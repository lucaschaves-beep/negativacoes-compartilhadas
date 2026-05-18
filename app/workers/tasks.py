import asyncio
import uuid
from datetime import datetime, timezone, date
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal, Card, Evidencia, Marca, Negativacao
from app.pipefy.client import PipefyClient
from app.pipefy.parser import parse_card_fields, filter_valid_attachments
from app.ai.vision import analyze_image
from app.ai.embeddings import generate_embedding, build_evidencia_text
from app.ai.storage import upload_to_r2, compute_hash


def run_async(coro):
    """Executa coroutine dentro do worker síncrono do Celery."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_card(self, card_id: str):
    """Task principal: lê card do Pipefy, parseia e enfileira análise dos anexos."""
    try:
        run_async(_process_card_async(card_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _process_card_async(card_id: str):
    pipefy = PipefyClient()
    card_raw = await pipefy.get_card(card_id)
    parsed = parse_card_fields(card_raw)
    attachments = filter_valid_attachments(card_raw)

    async with AsyncSessionLocal() as db:
        # Upsert do card
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

    # Enfileira análise de cada anexo
    for att in attachments:
        analyze_attachment.delay(card_id, att, parsed)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_attachment(self, card_id: str, attachment: dict, card_context: dict):
    """Baixa imagem, analisa com Gemini, salva evidência e detecta negativação."""
    try:
        run_async(_analyze_attachment_async(card_id, attachment, card_context))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _analyze_attachment_async(card_id: str, attachment: dict, card_context: dict):
    pipefy = PipefyClient()

    # Baixa imagem
    image_bytes = await pipefy.download_attachment(attachment["url"])
    file_hash = compute_hash(image_bytes)

    async with AsyncSessionLocal() as db:
        # Evita reprocessar o mesmo arquivo
        existing = await db.scalar(
            select(Evidencia).where(Evidencia.hash_arquivo == file_hash)
        )
        if existing:
            return

    # Analisa com Gemini Vision
    analysis = await analyze_image(image_bytes, card_context, attachment["filename"])

    # Faz upload para R2 (cache)
    url_cache = upload_to_r2(image_bytes, attachment["filename"], card_id)

    # Gera embedding
    text_for_embedding = build_evidencia_text(analysis, card_context)
    embedding = generate_embedding(text_for_embedding)

    # Converte data
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
            url_cache=url_cache,
            secao_origem=attachment.get("secao", "Anexos"),
            marca_identificada=analysis.get("marca_identificada"),
            concorrente_identificado=analysis.get("concorrente_identificado"),
            dominio=analysis.get("dominio"),
            plataforma=analysis.get("plataforma") or card_context.get("plataforma"),
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

        # Detecta e registra negativação se confirmada
        if analysis.get("confirmacao_negativacao"):
            await _register_negativacao(db, card_id, card_context, evidencia, analysis)

        # Marca card como processado
        card = await db.get(Card, card_id)
        if card:
            card.processado = True
            card.processed_at = datetime.now(timezone.utc)

        await db.commit()


async def _register_negativacao(db, card_id: str, card_context: dict, evidencia: Evidencia, analysis: dict):
    """Localiza ou cria marcas e registra a negativação no grafo."""
    nome_quem = analysis.get("marca_identificada") or card_context.get("cliente_mysql")
    nome_quem_foi = analysis.get("concorrente_identificado") or card_context.get("concorrente")

    if not nome_quem or not nome_quem_foi:
        return

    quem = await _get_or_create_marca(db, nome_quem)
    quem_foi = await _get_or_create_marca(db, nome_quem_foi)

    # Upsert da negativação
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
    result = await db.execute(
        select(Marca).where(Marca.nome.ilike(nome_clean))
    )
    marca = result.scalar_one_or_none()
    if not marca:
        marca = Marca(nome=nome_clean)
        db.add(marca)
        await db.flush()
    return marca
