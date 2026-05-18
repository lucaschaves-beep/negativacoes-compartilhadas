from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, text
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_db, Marca, Evidencia, Negativacao, Card, GrupoEmpresarial

router = APIRouter()


@router.get("/search")
async def search(
    q: str = Query(..., min_length=2, description="Nome de marca ou termo"),
    limite: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Busca inteligente por marca: retorna cards, evidências, negativações e boa fé.
    Combina busca textual + semântica (vetorial).
    """
    # 1. Busca textual por marca
    result = await db.execute(
        select(Marca).where(
            or_(
                Marca.nome.ilike(f"%{q}%"),
                Marca.nome_mysql.ilike(f"%{q}%"),
            )
        )
    )
    marcas = result.scalars().all()

    # 2. Busca textual nas evidências (full-text search)
    evidencias_result = await db.execute(
        text("""
            SELECT e.id, e.card_id, e.nome_logico, e.nome_original, e.url_cache, e.url_original,
                   e.marca_identificada, e.concorrente_identificado, e.plataforma,
                   e.confirmacao_negativacao, e.data_evidencia, e.tipo_evidencia, e.confianca,
                   NULL::float AS similaridade
            FROM evidencias e
            WHERE
                e.nome_logico ILIKE :q
                OR e.nome_original ILIKE :q
                OR e.marca_identificada ILIKE :q
                OR e.concorrente_identificado ILIKE :q
                OR e.ocr_raw ILIKE :q
                OR EXISTS (
                    SELECT 1 FROM UNNEST(e.termos_identificados) AS t WHERE t ILIKE :q
                )
            ORDER BY e.data_evidencia DESC NULLS LAST
            LIMIT :limite
        """),
        {"q": f"%{q}%", "limite": limite},
    )
    evidencias = [dict(row._mapping) for row in evidencias_result]

    # 3. Para cada marca encontrada, busca negativações e boa fé
    resposta_marcas = []
    for marca in marcas:
        # Cards relacionados
        cards_result = await db.execute(
            select(Card).where(
                or_(Card.cliente_id == marca.id, Card.concorrente_id == marca.id)
            ).order_by(Card.created_at.desc()).limit(10)
        )
        cards = cards_result.scalars().all()

        # Negativações que essa marca realizou
        neg_realizadas = await db.execute(
            select(Negativacao).where(Negativacao.quem_negativou_id == marca.id)
        )
        neg_realizadas = neg_realizadas.scalars().all()

        # Negativações que essa marca recebeu
        neg_recebidas = await db.execute(
            select(Negativacao).where(Negativacao.quem_foi_negativado_id == marca.id)
        )
        neg_recebidas = neg_recebidas.scalars().all()

        # Boa fé: marcas que têm negativação mútua com essa marca
        boa_fe_result = await db.execute(
            text("""
                SELECT ma.nome AS marca_a, mb.nome AS marca_b,
                       bfm.plataforma, bfm.a_negativou_em, bfm.b_negativou_em
                FROM boa_fe_mutua bfm
                JOIN marcas ma ON ma.id = bfm.marca_a_id
                JOIN marcas mb ON mb.id = bfm.marca_b_id
                WHERE bfm.marca_a_id = :mid OR bfm.marca_b_id = :mid
            """),
            {"mid": str(marca.id)},
        )
        boa_fe = [dict(row._mapping) for row in boa_fe_result]

        # Grupo empresarial
        grupo = None
        if marca.grupo_id:
            g = await db.get(GrupoEmpresarial, marca.grupo_id)
            if g:
                # Outras marcas do mesmo grupo
                outras_result = await db.execute(
                    select(Marca).where(
                        Marca.grupo_id == marca.grupo_id,
                        Marca.id != marca.id,
                    )
                )
                outras = outras_result.scalars().all()
                grupo = {
                    "id": str(g.id),
                    "nome": g.nome,
                    "outras_marcas": [{"id": str(m.id), "nome": m.nome} for m in outras],
                }

        resposta_marcas.append({
            "id": str(marca.id),
            "nome": marca.nome,
            "nome_mysql": marca.nome_mysql,
            "grupo": grupo,
            "cards_relacionados": [
                {
                    "id": c.id,
                    "titulo": c.titulo,
                    "fase": c.fase_atual,
                    "plataforma": c.plataforma,
                    "pipefy_url": c.pipefy_url,
                    "data": str(c.data_solicitacao) if c.data_solicitacao else None,
                }
                for c in cards
            ],
            "negativacoes_realizadas": len(neg_realizadas),
            "negativacoes_recebidas": len(neg_recebidas),
            "boa_fe": boa_fe,
        })

    return {
        "query": q,
        "marcas": resposta_marcas,
        "evidencias_semanticas": evidencias,
        "total_evidencias": len(evidencias),
    }


@router.get("/boa-fe")
async def check_boa_fe(
    marca_a: str = Query(...),
    marca_b: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Verifica se há boa fé mútua entre duas marcas específicas."""
    result_a = await db.execute(select(Marca).where(Marca.nome.ilike(f"%{marca_a}%")))
    m_a = result_a.scalar_one_or_none()

    result_b = await db.execute(select(Marca).where(Marca.nome.ilike(f"%{marca_b}%")))
    m_b = result_b.scalar_one_or_none()

    if not m_a or not m_b:
        raise HTTPException(status_code=404, detail="Uma ou ambas as marcas não encontradas")

    neg_a_b = await db.execute(
        select(Negativacao, Evidencia)
        .join(Evidencia, Negativacao.evidencia_id == Evidencia.id, isouter=True)
        .where(
            Negativacao.quem_negativou_id == m_a.id,
            Negativacao.quem_foi_negativado_id == m_b.id,
        )
    )
    neg_a_b = neg_a_b.all()

    neg_b_a = await db.execute(
        select(Negativacao, Evidencia)
        .join(Evidencia, Negativacao.evidencia_id == Evidencia.id, isouter=True)
        .where(
            Negativacao.quem_negativou_id == m_b.id,
            Negativacao.quem_foi_negativado_id == m_a.id,
        )
    )
    neg_b_a = neg_b_a.all()

    a_negativou_b = len(neg_a_b) > 0
    b_negativou_a = len(neg_b_a) > 0

    return {
        "marca_a": marca_a,
        "marca_b": marca_b,
        "boa_fe_completa": a_negativou_b and b_negativou_a,
        "a_negativou_b": a_negativou_b,
        "b_negativou_a": b_negativou_a,
        "evidencias_a_negativou_b": [
            {
                "card_id": n.card_id,
                "plataforma": n.plataforma,
                "data": str(n.data_negativacao) if n.data_negativacao else None,
                "evidencia_url": e.url_cache or e.url_original if e else None,
                "evidencia_nome": e.nome_logico if e else None,
            }
            for n, e in neg_a_b
        ],
        "evidencias_b_negativou_a": [
            {
                "card_id": n.card_id,
                "plataforma": n.plataforma,
                "data": str(n.data_negativacao) if n.data_negativacao else None,
                "evidencia_url": e.url_cache or e.url_original if e else None,
                "evidencia_nome": e.nome_logico if e else None,
            }
            for n, e in neg_b_a
        ],
    }


@router.get("/marcas")
async def list_marcas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Marca).order_by(Marca.nome))
    marcas = result.scalars().all()
    return [{"id": str(m.id), "nome": m.nome, "nome_mysql": m.nome_mysql} for m in marcas]


@router.post("/marcas/{marca_id}/grupo/{grupo_id}")
async def assign_grupo(marca_id: str, grupo_id: str, db: AsyncSession = Depends(get_db)):
    """Associa uma marca a um grupo empresarial."""
    marca = await db.get(Marca, marca_id)
    grupo = await db.get(GrupoEmpresarial, grupo_id)
    if not marca or not grupo:
        raise HTTPException(status_code=404, detail="Marca ou grupo não encontrado")
    marca.grupo_id = grupo_id
    await db.commit()
    return {"ok": True}
