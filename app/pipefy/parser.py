from app.config import get_settings

settings = get_settings()

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}


def _is_image(filename: str) -> bool:
    parts = filename.lower().rsplit('.', 1)
    return len(parts) > 1 and f'.{parts[1]}' in IMAGE_EXTENSIONS


FIELD_MAP = {
    "nome do concorrente": "concorrente",
    "concorrente": "concorrente",
    "nome cliente (mysql)": "cliente_mysql",
    "cliente mysql": "cliente_mysql",
    "cliente": "cliente_mysql",
    "termos negativados": "termos",
    "palavras negativadas": "termos",
    "plataforma": "plataforma",
    "status": "status",
    "grupo empresarial": "grupo",
    "empresa grupo": "grupo",
}

# Seções de anexo a IGNORAR
SECOES_IGNORAR = ["anexos do email", "email attachment", "email anexo"]


def parse_card_fields(card: dict) -> dict:
    result = {
        "id": card["id"],
        "titulo": card.get("title", ""),
        "fase_atual": card.get("current_phase", {}).get("name", ""),
        "data_solicitacao": card.get("createdAt", "")[:10] if card.get("createdAt") else None,
        "concorrente": None,
        "cliente_mysql": None,
        "termos": [],
        "plataforma": None,
        "status": None,
        "grupo": None,
        "pipefy_url": f"https://app.pipefy.com/open-cards/{card['id']}",
        "raw_data": card,
    }

    for field in card.get("fields", []):
        label = (field.get("name") or field.get("field", {}).get("label") or "").lower().strip()
        value = field.get("value") or ""
        array_value = field.get("array_value") or []

        key = FIELD_MAP.get(label)
        if not key:
            continue

        if key == "termos":
            result["termos"] = array_value if array_value else [v.strip() for v in value.split(",") if v.strip()]
        else:
            result[key] = value.strip() if value else None

    return result


def _build_uuid_url_map(card: dict) -> dict[str, str]:
    """
    Cria mapa de UUID → URL assinada a partir de card.attachments.
    card.attachments contém URLs completas e assinadas do Pipefy Storage.
    """
    uuid_map = {}
    for att in card.get("attachments", []):
        url = att.get("url", "")
        if not url:
            continue
        # Extrai UUID do path: .../signed/uploads/{uuid}/filename.ext?...
        parts = url.split("/uploads/")
        if len(parts) > 1:
            uuid = parts[1].split("/")[0]
            uuid_map[uuid] = url
    return uuid_map


def filter_valid_attachments(card: dict) -> list[dict]:
    """
    Retorna anexos válidos com URLs assinadas completas.
    Usa campos de attachment para identificar a seção,
    e card.attachments para obter as URLs corretas.
    """
    uuid_url_map = _build_uuid_url_map(card)
    valid_attachments = []
    seen_urls = set()

    # 1. Anexos de campos com seção válida (ex: "N1AP. G. Ads - Print da negativação")
    for field in card.get("fields", []):
        label = (field.get("name") or field.get("field", {}).get("label") or "").strip()
        label_lower = label.lower()

        # Ignora seção de e-mail
        if any(ignorar in label_lower for ignorar in SECOES_IGNORAR):
            continue

        # Aceita campos de seção válida
        is_valid_section = any(
            secao.lower() in label_lower or label_lower in secao.lower()
            for secao in settings.secoes_validas
        )
        if not is_valid_section:
            continue

        for path in (field.get("array_value") or []):
            if not path:
                continue
            # Extrai UUID do path relativo: uploads/{uuid}/filename
            # Path pode ser "uploads/uuid/file" ou "/uploads/uuid/file"
            clean = path.lstrip("/")
            if clean.startswith("uploads/"):
                uuid = clean.split("/")[1]
            else:
                parts = clean.split("/uploads/")
                uuid = parts[1].split("/")[0] if len(parts) > 1 else None
            filename = path.split("/")[-1].split("?")[0]

            signed_url = uuid_url_map.get(uuid) if uuid else None
            if not signed_url:
                # Tenta construir URL diretamente
                signed_url = f"https://app.pipefy.com/storage/v1/signed/{path.lstrip('/')}"

            if signed_url and signed_url not in seen_urls and _is_image(filename):
                seen_urls.add(signed_url)
                valid_attachments.append({
                    "url": signed_url,
                    "filename": filename,
                    "secao": label,
                })

    # 2. Fallback: usa card.attachments diretos (seção "Anexos")
    #    Inclui apenas os que ainda não foram adicionados
    if not valid_attachments:
        for att in card.get("attachments", []):
            url = att.get("url", "")
            if url and url not in seen_urls:
                filename = url.split("/")[-1].split("?")[0]
                if not _is_image(filename):
                    continue
                seen_urls.add(url)
                valid_attachments.append({
                    "url": url,
                    "filename": filename,
                    "secao": "Anexos",
                })

    return valid_attachments
