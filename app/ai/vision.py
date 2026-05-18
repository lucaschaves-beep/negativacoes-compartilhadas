import json
import re
import io
import base64
from PIL import Image
import httpx
from app.config import get_settings

settings = get_settings()

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

PROMPT_ANALISE = """Você é um especialista em análise de evidências de negativação de palavras-chave em plataformas de anúncios digitais (Google Ads, Bing Ads, Microsoft Ads).

Contexto do card:
- Cliente solicitante: {cliente}
- Concorrente (que deveria ser negativado): {concorrente}
- Plataforma informada no card: {plataforma}

Analise a imagem e retorne APENAS um JSON com esta estrutura:
{{
  "marca_identificada": "nome da marca/empresa visível",
  "concorrente_identificado": "nome do concorrente negativado, se visível",
  "dominio": "domínio ou URL visível, ou null",
  "plataforma": "Google Ads | Bing Ads | Microsoft Ads | outro",
  "termos_identificados": ["termos", "negativados", "visíveis"],
  "tipo_evidencia": "confirmacao_negativacao | lista_termos | bloqueio_ativo | campanha | outro",
  "data_evidencia": "YYYY-MM-DD ou null",
  "confirmacao_negativacao": true,
  "confianca": 0.85,
  "ocr_raw": "todo o texto extraído da imagem",
  "nome_logico": "Negativação Serasa x AcordoCerto - Google Ads - Abr 2026",
  "observacoes": "observações relevantes"
}}

Regras:
- termos_identificados nunca null, use [] se vazio
- confirmacao_negativacao = true somente se o print mostra negativação salva/ativa
- Responda APENAS com o JSON, sem texto adicional"""


async def analyze_image(
    image_bytes: bytes,
    card_context: dict,
    filename: str = "",
) -> dict:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Redimensiona se muito grande (limite Groq: 4MB por imagem)
        max_size = 1280
        if max(image.size) > max_size:
            image.thumbnail((max_size, max_size), Image.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_b64 = base64.b64encode(buffer.getvalue()).decode()

        prompt = PROMPT_ANALISE.format(
            cliente=card_context.get("cliente_mysql") or "não informado",
            concorrente=card_context.get("concorrente") or "não informado",
            plataforma=card_context.get("plataforma") or "não informado",
        )

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GROQ_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

        raw_text = data["choices"][0]["message"]["content"].strip()
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        result = json.loads(raw_text)
        result.setdefault("termos_identificados", [])
        result.setdefault("confirmacao_negativacao", False)
        result.setdefault("confianca", 0.5)
        result.setdefault("ocr_raw", "")
        result.setdefault("nome_logico", _fallback_nome_logico(card_context, filename))

        return result

    except json.JSONDecodeError:
        return _empty_analysis(card_context, filename, error="JSON inválido retornado pelo Groq")
    except Exception as e:
        return _empty_analysis(card_context, filename, error=str(e))


def _fallback_nome_logico(card_context: dict, filename: str) -> str:
    cliente = card_context.get("cliente_mysql") or "?"
    concorrente = card_context.get("concorrente") or "?"
    plataforma = card_context.get("plataforma") or "?"
    return f"Negativação {cliente} x {concorrente} - {plataforma} - {filename}"


def _empty_analysis(card_context: dict, filename: str, error: str = "") -> dict:
    return {
        "marca_identificada": None,
        "concorrente_identificado": None,
        "dominio": None,
        "plataforma": card_context.get("plataforma"),
        "termos_identificados": [],
        "tipo_evidencia": "outro",
        "data_evidencia": None,
        "confirmacao_negativacao": False,
        "confianca": 0.0,
        "ocr_raw": "",
        "nome_logico": _fallback_nome_logico(card_context, filename),
        "observacoes": f"Erro na análise: {error}",
    }
