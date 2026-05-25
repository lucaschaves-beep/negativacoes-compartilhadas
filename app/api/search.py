from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, text

from app.database import get_db, Marca, Evidencia, Negativacao, Card, GrupoEmpresarial

router = APIRouter()


@router.get("/search")
async def search(
    q: str = Query(..., min_length=2, description="Nome de marca ou termo"),
    limite: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
):
    q_like = f"%{q}%"

    # 1. Busca por marca
    result = await db.execute(
        select(Marca).where(
            or_(
                Marca.nome.ilike(q_like),
                Marca.nome_mysql.ilike(q_like),
            )
        )
    )
    marcas = result.scalars().all()

    # 2. Busca nas evidências — exclui análises que falharam (confianca=0.0)
    ev_result = await db.execute(
        select(
            Evidencia.id,
            Evidencia.card_id,
            Evidencia.nome_logico,
            Evidencia.nome_original,
            Evidencia.url_cache,
            Evidencia.url_original,
            Evidencia.marca_identificada,
            Evidencia.concorrente_identificado,
            Evidencia.plataforma,
            Evidencia.tipo_acao,
            Evidencia.tipo_correspondencia,
            Evidencia.nivel_aplicacao,
            Evidencia.confirmacao_negativacao,
            Evidencia.data_evidencia,
            Evidencia.tipo_evidencia,
            Evidencia.confianca,
        ).where(
            Evidencia.confianca > 0,
            or_(
                Evidencia.nome_logico.ilike(q_like),
                Evidencia.nome_original.ilike(q_like),
                Evidencia.marca_identificada.ilike(q_like),
                Evidencia.concorrente_identificado.ilike(q_like),
                Evidencia.ocr_raw.ilike(q_like),
            )
        ).order_by(Evidencia.data_evidencia.desc().nullslast()).limit(limite)
    )
    evidencias = [
        {
            "id": str(row.id),
            "card_id": row.card_id,
            "nome_logico": row.nome_logico,
            "nome_original": row.nome_original,
            "url_cache": row.url_cache,
            "url_original": row.url_original,
            "marca_identificada": row.marca_identificada,
            "concorrente_identificado": row.concorrente_identificado,
            "plataforma": row.plataforma,
            "tipo_acao": row.tipo_acao,
            "tipo_correspondencia": row.tipo_correspondencia,
            "nivel_aplicacao": row.nivel_aplicacao,
            "confirmacao_negativacao": row.confirmacao_negativacao,
            "data_evidencia": str(row.data_evidencia) if row.data_evidencia else None,
            "tipo_evidencia": row.tipo_evidencia,
            "confianca": row.confianca,
            "similaridade": None,
        }
        for row in ev_result
    ]

    # 3. Para cada marca encontrada, busca cards e negativações
    resposta_marcas = []
    for marca in marcas:
        # Cards relacionados — busca pelos nomes raw (cliente_id/concorrente_id nunca populados)
        cards_result = await db.execute(
            select(Card).where(
                or_(
                    Card.nome_cliente_mysql_raw.ilike(f"%{marca.nome}%"),
                    Card.nome_concorrente_raw.ilike(f"%{marca.nome}%"),
                )
            ).order_by(Card.created_at.desc()).limit(10)
        )
        cards = cards_result.scalars().all()

        neg_realizadas = await db.execute(
            select(Negativacao).where(Negativacao.quem_negativou_id == marca.id)
        )
        neg_realizadas = neg_realizadas.scalars().all()

        neg_recebidas = await db.execute(
            select(Negativacao).where(Negativacao.quem_foi_negativado_id == marca.id)
        )
        neg_recebidas = neg_recebidas.scalars().all()

        mid = str(marca.id)
        boa_fe_result = await db.execute(
            text("""
                SELECT ma.nome AS marca_a, mb.nome AS marca_b,
                       bfm.plataforma, bfm.a_negativou_em, bfm.b_negativou_em
                FROM boa_fe_mutua bfm
                JOIN marcas ma ON ma.id = bfm.marca_a_id
                JOIN marcas mb ON mb.id = bfm.marca_b_id
                WHERE bfm.marca_a_id = :mid1 OR bfm.marca_b_id = :mid2
            """),
            {"mid1": mid, "mid2": mid},
        )
        boa_fe = [dict(row._mapping) for row in boa_fe_result]

        grupo = None
        if marca.grupo_id:
            g = await db.get(GrupoEmpresarial, marca.grupo_id)
            if g:
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
    # Usa .scalars().first() para não quebrar quando há múltiplas marcas com nome similar
    result_a = await db.execute(select(Marca).where(Marca.nome.ilike(f"%{marca_a}%")))
    m_a = result_a.scalars().first()

    result_b = await db.execute(select(Marca).where(Marca.nome.ilike(f"%{marca_b}%")))
    m_b = result_b.scalars().first()

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
    marca = await db.get(Marca, marca_id)
    grupo = await db.get(GrupoEmpresarial, grupo_id)
    if not marca or not grupo:
        raise HTTPException(status_code=404, detail="Marca ou grupo não encontrado")
    marca.grupo_id = grupo_id
    await db.commit()
    return {"ok": True}
