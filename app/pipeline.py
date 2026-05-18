"""
Pipeline de processamento de cards — sem Celery, roda diretamente via async.
Usado pelo webhook (BackgroundTasks) e pelos scripts manuais.
"""
import hashlib
from datetime import datetime, timezone, date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import AsyncSessionLocal, Card, Evidencia, Marca, Negativacao
from app.pipefy.client import PipefyClient
from app.pipefy.parser import parse_card_fields, filter_valid_attachments
from app.ai.vision import analyze_image
from app.ai.embeddings import generate_embedding, build_evidencia_text
from app.ai.storage import upload_to_r2, compute_hash


async def processar_card(card_id: str):
    """Lê card do Pipefy, analisa anexos e salva no banco."""
    pipefy = PipefyClient()
    card_raw = await pipefy.get_card(card_id)
    parsed = parse_card_fields(card_raw)
    attachments = filter_valid_attachments(card_raw)

    async with AsyncSessionLocal() as db:
        stmt = pg_insert(Card).values(
            id=card_id,
            pipefy_url=parsed["pipefy_url"],
            titulo=parsed["titulo"],
            nome_concorrente_raw=parsed.get("concorrente"),
            nome_cliente_mysql_raw=parsed.get("cliente_mysql"),
            termos_negativados=parsed.get("termos", []),
            plataforma=parsed.get("plataforma"),
            status=parsed.get("status"),
            fase_atual=parsed.get("fase_atual"),
            data_solicitacao=parsed.get("data_solicitacao"),
            raw_data=parsed["raw_data"],
            processado=False,
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={
                "raw_data": parsed["raw_data"],
                "fase_atual": parsed.get("fase_atual"),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        await db.execute(stmt)
        await db.commit()

    for att in attachments:
        await processar_anexo(card_id, att, parsed)


async def processar_anexo(card_id: str, attachment: dict, card_context: dict):
    """Baixa imagem, analisa com Groq, salva evidência."""
    pipefy = PipefyClient()
    image_bytes = await pipefy.download_attachment(attachment["url"])
    file_hash = compute_hash(image_bytes)

    async with AsyncSessionLocal() as db:
        existing = await db.scalar(
            select(Evidencia).where(Evidencia.hash_arquivo == file_hash)
        )
        if existing:
            return  # já processado, não gasta crédito

    analysis = await analyze_image(image_bytes, card_context, attachment["filename"])
    url_cache = upload_to_r2(image_bytes, attachment["filename"], card_id)

    text_for_embedding = build_evidencia_text(analysis, card_context)
    embedding = generate_embedding(text_for_embedding)

    data_ev = None
    if analysis.get("data_evidencia"):
        try:
            data_ev = date.fromisoformat(analysis["data_evidencia"])
        except (ValueError, TypeError):
            pass

    async with AsyncSessionLocal() as db:
        evidencia = Evidencia(
            card_id=card_id,
            nome_original=attachment["filename"],
            nome_logico=analysis.get("nome_logico"),
            url_original=attachment["url"],
            url_cache=url_cache or None,
            secao_origem=attachment.get("secao", "Anexos"),
            marca_identificada=analysis.get("marca_identificada"),
            concorrente_identificado=analysis.get("concorrente_identificado"),
            dominio=analysis.get("dominio"),
            plataforma=analysis.get("plataforma") or card_context.get("plataforma"),
            tipo_acao=analysis.get("tipo_acao", "negativacao"),
            tipo_correspondencia=analysis.get("tipo_correspondencia"),
            nivel_aplicacao=analysis.get("nivel_aplicacao"),
            termos_identificados=analysis.get("termos_identificados", []),
            tipo_evidencia=analysis.get("tipo_evidencia"),
            data_evidencia=data_ev,
            confirmacao_negativacao=analysis.get("confirmacao_negativacao", False),
            confianca=analysis.get("confianca", 0.0),
            ocr_raw=analysis.get("ocr_raw", ""),
            analise_ia=analysis,
            embedding=embedding,
            hash_arquivo=file_hash,
        )
        db.add(evidencia)
        await db.flush()

        if analysis.get("confirmacao_negativacao"):
            await _registrar_negativacao(db, card_id, card_context, evidencia, analysis)

        card = await db.get(Card, card_id)
        if card:
            card.processado = True
            card.processed_at = datetime.now(timezone.utc)

        await db.commit()


async def _registrar_negativacao(db, card_id, card_context, evidencia, analysis):
    nome_quem = analysis.get("marca_identificada") or card_context.get("cliente_mysql")
    nome_quem_foi = analysis.get("concorrente_identificado") or card_context.get("concorrente")
    if not nome_quem or not nome_quem_foi:
        return

    quem = await _get_or_create_marca(db, nome_quem)
    quem_foi = await _get_or_create_marca(db, nome_quem_foi)

    stmt = pg_insert(Negativacao).values(
        quem_negativou_id=quem.id,
        quem_foi_negativado_id=quem_foi.id,
        evidencia_id=evidencia.id,
        card_id=card_id,
        plataforma=analysis.get("plataforma") or card_context.get("plataforma"),
        data_negativacao=evidencia.data_evidencia,
        confirmada=True,
    ).on_conflict_do_nothing()
    await db.execute(stmt)


async def _get_or_create_marca(db, nome: str) -> Marca:
    nome_clean = nome.strip()
    result = await db.execute(select(Marca).where(Marca.nome.ilike(nome_clean)))
    marca = result.scalar_one_or_none()
    if not marca:
        marca = Marca(nome=nome_clean)
        db.add(marca)
        await db.flush()
    return marca
