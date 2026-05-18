from fastapi import APIRouter
from app.pipefy.client import PipefyClient
from app.pipefy.parser import parse_card_fields
from app.clients import FASES_SYNC, FASE_SUCESSO_ID, is_cliente
from app.pipeline import processar_card

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
async def process_sync(card_id: str):
    """Processa um card de forma síncrona (aguarda conclusão)."""
    try:
        await processar_card(card_id)
        return {"ok": True, "card_id": card_id}
    except Exception as e:
        return {"ok": False, "card_id": card_id, "error": str(e)}
