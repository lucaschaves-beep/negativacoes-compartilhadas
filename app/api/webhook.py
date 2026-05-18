import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from app.config import get_settings
from app.pipeline import processar_card

router = APIRouter()
settings = get_settings()


def _verify_signature(body: bytes, signature: str) -> bool:
    if not settings.webhook_secret:
        return True
    expected = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


@router.post("/webhook/pipefy")
async def pipefy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_pipefy_signature: str = Header(default=""),
):
    body = await request.body()

    if not _verify_signature(body, x_pipefy_signature):
        raise HTTPException(status_code=401, detail="Assinatura inválida")

    payload = await request.json()
    data = payload.get("data", {})
    action = data.get("action", "")

    if action in ("card.create", "card.update", "card.move"):
        card_id = str(data.get("card", {}).get("id", ""))
        if card_id:
            background_tasks.add_task(processar_card, card_id)
            return {"ok": True, "card_id": card_id, "action": action}

    return {"ok": True, "skipped": True}


@router.post("/webhook/process/{card_id}")
async def manual_process(card_id: str, background_tasks: BackgroundTasks):
    """Força reprocessamento manual de um card específico."""
    background_tasks.add_task(processar_card, card_id)
    return {"ok": True, "card_id": card_id, "queued": True}
