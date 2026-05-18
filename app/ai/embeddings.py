def generate_embedding(text: str) -> list[float]:
    """No-op — vector search replaced by full-text search to avoid heavy ML deps."""
    return []


def build_evidencia_text(analysis: dict, card_context: dict) -> str:
    """Constrói texto rico para indexação da evidência."""
    parts = []

    if analysis.get("nome_logico"):
        parts.append(analysis["nome_logico"])
    if analysis.get("marca_identificada"):
        parts.append(f"marca: {analysis['marca_identificada']}")
    if analysis.get("concorrente_identificado"):
        parts.append(f"concorrente: {analysis['concorrente_identificado']}")
    if analysis.get("plataforma"):
        parts.append(f"plataforma: {analysis['plataforma']}")
    if analysis.get("termos_identificados"):
        parts.append(f"termos: {', '.join(analysis['termos_identificados'])}")
    if analysis.get("tipo_evidencia"):
        parts.append(f"tipo: {analysis['tipo_evidencia']}")
    if analysis.get("ocr_raw"):
        parts.append(analysis["ocr_raw"][:500])
    if card_context.get("concorrente"):
        parts.append(f"concorrente card: {card_context['concorrente']}")
    if card_context.get("cliente_mysql"):
        parts.append(f"cliente: {card_context['cliente_mysql']}")

    return " | ".join(parts)
