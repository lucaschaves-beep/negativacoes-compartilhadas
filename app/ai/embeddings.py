from sentence_transformers import SentenceTransformer
import numpy as np
from functools import lru_cache

# Modelo leve, gratuito, 384 dimensões — roda local sem GPU
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def generate_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        return [0.0] * 384

    model = _get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def build_evidencia_text(analysis: dict, card_context: dict) -> str:
    """Constrói texto rico para vetorização da evidência."""
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
        # Limita OCR para não poluir o embedding
        parts.append(analysis["ocr_raw"][:500])
    if card_context.get("concorrente"):
        parts.append(f"concorrente card: {card_context['concorrente']}")
    if card_context.get("cliente_mysql"):
        parts.append(f"cliente: {card_context['cliente_mysql']}")

    return " | ".join(parts)
