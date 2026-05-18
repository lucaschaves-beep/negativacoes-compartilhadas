from fastapi import APIRouter
from pydantic import BaseModel
from app.pipefy.client import PipefyClient
from app.pipefy.parser import parse_card_fields
from app.clients import FASES_SYNC, FASE_SUCESSO_ID, is_cliente
from app.pipeline import salvar_card, processar_anexo

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/sync/fases")
async def listar_fases():
    return {"fases": FASES_SYNC}


@router.get("/sync/scan")
async def scan_fase(phase_id: str, cursor: str = None):
    """
    Escaneia uma página (50 cards) de uma fase do Pipefy.
    Para a fase Sucesso, filtra apenas cards onde o concorrente é cliente Branddi.
    Retorna IDs a processar + cursor para a próxima página.
    """
    pipefy = PipefyClient()
    result = await pipefy.list_phase_cards_page(phase_id, cursor or None)

    filtrar = phase_id == FASE_SUCESSO_ID
    matched_ids = []

    for card in result["cards"]:
        if filtrar:
            parsed = parse_card_fields(card)
            concorrente = parsed.get("concorrente") or ""
            if not is_cliente(concorrente):
                continue
        matched_ids.append(card["id"])

    return {
        "matched_ids": matched_ids,
        "scanned": len(result["cards"]),
        "matched": len(matched_ids),
        "has_next": result["has_next"],
        "next_cursor": result["next_cursor"],
        "total": result["total"],
    }


@router.post("/process/{card_id}")
async def process_save_card(card_id: str):
    """
    Passo 1 da sincronização: salva metadados do card no banco e retorna
    a lista de anexos para o frontend processar um por um.
    Rápido (~2-3s) — sem chamadas de IA.
    """
    try:
        attachments, card_context = await salvar_card(card_id)
        return {
            "ok": True,
            "card_id": card_id,
            "attachments": attachments,
            "card_context": card_context,
        }
    except Exception as e:
        return {"ok": False, "card_id": card_id, "error": str(e)}


class AnexoPayload(BaseModel):
    card_id: str
    attachment: dict
    card_context: dict


@router.post("/process-attachment")
async def process_single_attachment(payload: AnexoPayload):
    """
    Passo 2 da sincronização: processa UM anexo com Groq Vision (~10-20s).
    O frontend chama este endpoint para cada anexo separadamente,
    evitando o timeout de 60s do Vercel.
    """
    try:
        await processar_anexo(payload.card_id, payload.attachment, payload.card_context)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
