IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}

# Seções de anexo a IGNORAR (email recebido — não são evidências)
SECOES_IGNORAR = ["anexos do email", "email attachment", "email anexo"]

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


def _is_image(filename: str) -> bool:
    parts = filename.lower().rsplit('.', 1)
    return len(parts) > 1 and f'.{parts[1]}' in IMAGE_EXTENSIONS


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


def filter_valid_attachments(card: dict) -> list[dict]:
    """
    Retorna todas as imagens do card excluindo as de seções de e-mail.
    Usa card.attachments (URLs assinadas) como fonte primária — garante capturar
    imagens de qualquer seção válida (Google Ads, Bing, etc.) sem depender de
    nomes de seção fixos.
    """
    # Coleta UUIDs das seções ignoradas (e-mail) para excluir
    ignored_uuids: set[str] = set()
    for field in card.get("fields", []):
        label = (field.get("name") or field.get("field", {}).get("label") or "").lower().strip()
        if any(ign in label for ign in SECOES_IGNORAR):
            for path in (field.get("array_value") or []):
                if not path:
                    continue
                clean = path.lstrip("/")
                if "uploads/" in clean:
                    uuid_part = clean.split("uploads/", 1)[1].split("/")[0]
                    if uuid_part:
                        ignored_uuids.add(uuid_part)

    # Retorna todas as imagens que não são de seções ignoradas
    valid: list[dict] = []
    seen: set[str] = set()
    for att in card.get("attachments", []):
        url = att.get("url", "")
        if not url or url in seen:
            continue
        if "/uploads/" in url:
            uuid_part = url.split("/uploads/", 1)[1].split("/")[0]
            if uuid_part in ignored_uuids:
                continue
        filename = url.split("/")[-1].split("?")[0]
        if not _is_image(filename):
            continue
        seen.add(url)
        valid.append({"url": url, "filename": filename, "secao": "Anexos"})
    return valid
