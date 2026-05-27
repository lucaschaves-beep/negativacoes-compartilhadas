IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}

SECOES_IGNORAR = ["anexos do email", "email attachment", "email anexo"]

# Mapeamento por ID do campo (estável, preferido sobre label)
FIELD_ID_MAP = {
    "copy_of_dom_nio_do_concorrente": "concorrente",
    "nome_cliente_mysql": "cliente_mysql",
    "plataforma": "plataforma",
    "canal_da_ocor_ncia": "canal",
    "canais_de_ocorr_ncia_novos_canais_1": "canal",
    "outros_termos_para_negativar": "termos",
    "palavras_chave_monitoraras": "termos",
    "tipo_de_concorrente": "tipo_concorrente",
    "negativa_o_boa_f_via_bms": "boa_fe_bms",
    "negativa_o_boa_f_via_plataforma": "boa_fe_plataforma",
    # Datas de confirmação por plataforma (auxiliam o contexto da IA)
    "copy_of_data_da_ltima_resposta_do_concorrente_1": "data_confirmacao",
    "copy_of_data_da_ltima_confirma_o_de_negativa_o": "data_confirmacao_google",
    "copy_of_data_da_ltima_confirma_o_de_negativa_o_google": "data_confirmacao_bing",
    "copy_of_data_da_ltima_confirma_o_de_negativa_o_bing": "data_confirmacao_asa",
    "copy_of_data_da_ltima_confirma_o_de_negativa_o_asa": "data_confirmacao_playstore",
    "copy_of_data_da_ltima_confirma_o_de_negativa_o_play_store": "data_confirmacao_amazon",
}

# Fallback por label (para campos não mapeados por ID)
FIELD_LABEL_MAP = {
    "nome do concorrente": "concorrente",
    "concorrente": "concorrente",
    "nome cliente (mysql)": "cliente_mysql",
    "cliente mysql": "cliente_mysql",
    "cliente": "cliente_mysql",
    "termos negativados": "termos",
    "palavras negativadas": "termos",
    "outros termos para negativar": "termos",
    "plataforma": "plataforma",
    "status": "status",
    "grupo empresarial": "grupo",
    "empresa grupo": "grupo",
}

# IDs de campos que contêm prints de evidência → metadata de plataforma/seção
PRINT_FIELDS: dict[str, dict] = {
    "print_da_negativa_o":                    {"plataforma": "Google Ads",      "secao": "N1AP. G. Ads - Print da negativação"},
    "g_shopping_n1ap_print_da_negativa_o":    {"plataforma": "Google Shopping", "secao": "N1AP. G. Shopping - Print da negativação"},
    "n1ap_q_print_da_negativa_o":             {"plataforma": None,              "secao": "N1AP_Q. Print da negativação"},
    "n1pr1_print_da_evid_ncia":               {"plataforma": None,              "secao": "N1PR. Print da Evidência"},
    "copy_of_print_data_studio":              {"plataforma": "Google Ads",      "secao": "N1T1. G. Ads - Print da Evidência"},
    "copy_of_n1t1_print_da_evid_ncia":        {"plataforma": "Google Shopping", "secao": "N1T1. G. Shopping - Print da Evidência"},
    "copy_of_n1t1_g_ads_print_da_evid_ncia":  {"plataforma": "Google Ads",      "secao": "N1T1. G. Ads - Print da Evidência (cópia)"},
    "copy_of_n1t1_g_shopping_print_da_evid_ncia": {"plataforma": "Bing Shopping", "secao": "N1T1. B. Shopping - Print da Evidência"},
    "print_da_evid_ncia":                     {"plataforma": None,              "secao": "Print da Evidência"},
    "print_da_evid_ncia_bing_ads_novos_canais": {"plataforma": "Bing Ads",      "secao": "Print da evidência [Novos Canais]"},
    "top_leil_o_anexo_evid_ncia":             {"plataforma": None,              "secao": "Top Leilão - Evidência"},
}


def _is_image(filename: str) -> bool:
    parts = filename.lower().rsplit('.', 1)
    return len(parts) > 1 and f'.{parts[1]}' in IMAGE_EXTENSIONS


def _field_id(field: dict) -> str:
    return (field.get("field") or {}).get("id") or ""


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
        "canal": None,
        "tipo_concorrente": None,
        "boa_fe_bms": None,
        "boa_fe_plataforma": None,
        "data_confirmacao": None,
        "data_confirmacao_google": None,
        "data_confirmacao_bing": None,
        "data_confirmacao_asa": None,
        "data_confirmacao_playstore": None,
        "data_confirmacao_amazon": None,
        "status": None,
        "grupo": None,
        "pipefy_url": f"https://app.pipefy.com/open-cards/{card['id']}",
        "raw_data": card,
    }

    for field in card.get("fields", []):
        fid = _field_id(field)
        label = (field.get("name") or field.get("field", {}).get("label") or "").lower().strip()
        value = field.get("value") or ""
        array_value = field.get("array_value") or []

        key = FIELD_ID_MAP.get(fid) or FIELD_LABEL_MAP.get(label)
        if not key:
            continue

        if key == "termos":
            novos = array_value if array_value else [v.strip() for v in value.split(",") if v.strip()]
            result["termos"] = list(set(result["termos"] + novos))
        else:
            result[key] = value.strip() if value else None

    return result


def filter_valid_attachments(card: dict) -> list[dict]:
    """
    Retorna imagens do card excluindo seções de e-mail.
    Enriquece cada anexo com plataforma_hint e secao quando o campo de origem
    é um campo de print conhecido (ex: N1AP. G. Ads - Print da negativação).
    """
    uuid_meta: dict[str, dict] = {}
    ignored_uuids: set[str] = set()

    for field in card.get("fields", []):
        fid = _field_id(field)
        label = (field.get("name") or field.get("field", {}).get("label") or "").lower().strip()
        paths = field.get("array_value") or []

        is_email = any(ign in label for ign in SECOES_IGNORAR)
        is_print = fid in PRINT_FIELDS

        for path in paths:
            if not path:
                continue
            clean = path.lstrip("/")
            if "uploads/" not in clean:
                continue
            uuid_part = clean.split("uploads/", 1)[1].split("/")[0]
            if not uuid_part:
                continue
            if is_email:
                ignored_uuids.add(uuid_part)
            elif is_print and uuid_part not in uuid_meta:
                uuid_meta[uuid_part] = PRINT_FIELDS[fid]

    valid: list[dict] = []
    seen: set[str] = set()
    for att in card.get("attachments", []):
        url = att.get("url", "")
        if not url or url in seen:
            continue
        uuid_part = None
        if "/uploads/" in url:
            uuid_part = url.split("/uploads/", 1)[1].split("/")[0]
            if uuid_part in ignored_uuids:
                continue
        filename = url.split("/")[-1].split("?")[0]
        if not _is_image(filename):
            continue
        meta = uuid_meta.get(uuid_part or "", {})
        seen.add(url)
        valid.append({
            "url": url,
            "filename": filename,
            "secao": meta.get("secao", "Anexos"),
            "plataforma_hint": meta.get("plataforma"),
        })
    return valid
