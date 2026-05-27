import asyncio
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

PROMPT_ANALISE = """Você é um especialista em análise de evidências de negativação e exclusão de marcas em plataformas de anúncios digitais (Google Ads, Bing Ads).

Contexto do card:
{contexto_linhas}

Analise a imagem e retorne APENAS um JSON com esta estrutura:
{{
  "marca_identificada": "nome da marca/empresa que fez a ação",
  "concorrente_identificado": "nome do concorrente alvo da ação",
  "dominio": "domínio ou URL visível, ou null",
  "plataforma": "Google Ads | Google Shopping | Bing Ads | Bing Shopping | Microsoft Ads | outro",
  "tipo_acao": "negativacao | exclusao_marca",
  "tipo_correspondencia": "exata | frase | ampla | null",
  "nivel_aplicacao": "conta | campanha | grupo_anuncios | null",
  "termos_identificados": ["termos", "negativados", "visíveis"],
  "tipo_evidencia": "confirmacao_negativacao | lista_termos | bloqueio_ativo | campanha | outro",
  "data_evidencia": "YYYY-MM-DD ou null",
  "confirmacao_negativacao": true,
  "confianca": 0.85,
  "ocr_raw": "todo o texto extraído da imagem",
  "nome_logico": "Negativação Serasa x AcordoCerto - Google Ads - Exata - Conta - Abr 2026",
  "observacoes": "observações relevantes"
}}

Regras:
- tipo_acao: "negativacao" = palavras-chave negativas; "exclusao_marca" = exclusão de marca (Brand Exclusions no Google Ads / Bing)
- tipo_correspondencia: "exata" = [colchetes], "frase" = "aspas", "ampla" = sem marcação; null se exclusão de marca
- nivel_aplicacao: "conta" = lista compartilhada/nível de conta; "campanha" = aplicado em campanha específica; null se não identificado
- termos_identificados nunca null, use [] se vazio
- Se o contexto informa a plataforma do campo de origem, use-a como forte indicativo
- Se o contexto informa termos negativados, procure-os na imagem
- confirmacao_negativacao = true somente se o print mostra negativação/exclusão salva ou ativa
- Responda APENAS com o JSON, sem texto adicional"""


def _build_contexto(card_context: dict, plataforma_hint: str | None) -> str:
    lines = []
    if card_context.get("cliente_mysql"):
        lines.append(f"- Cliente solicitante: {card_context['cliente_mysql']}")
    if card_context.get("concorrente"):
        lines.append(f"- Concorrente (alvo da negativação): {card_context['concorrente']}")
    if plataforma_hint:
        lines.append(f"- Plataforma (identificada pelo campo do card): {plataforma_hint}")
    elif card_context.get("plataforma"):
        lines.append(f"- Plataforma informada no card: {card_context['plataforma']}")
    if card_context.get("tipo_concorrente"):
        lines.append(f"- Tipo de concorrente: {card_context['tipo_concorrente']}")
    termos = card_context.get("termos") or []
    if termos:
        lines.append(f"- Termos negativados (do card): {', '.join(termos[:15])}")
    datas = [
        ("Google", card_context.get("data_confirmacao_google")),
        ("Bing", card_context.get("data_confirmacao_bing")),
        ("ASA", card_context.get("data_confirmacao_asa")),
    ]
    for plat, data in datas:
        if data:
            lines.append(f"- Data confirmação {plat} (campo estruturado): {data}")
    return "\n".join(lines) if lines else "- Sem contexto adicional"


async def analyze_image(
    image_bytes: bytes,
    card_context: dict,
    filename: str = "",
    plataforma_hint: str | None = None,
) -> dict:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        max_size = 1280
        if max(image.size) > max_size:
            image.thumbnail((max_size, max_size), Image.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_b64 = base64.b64encode(buffer.getvalue()).decode()

        prompt = PROMPT_ANALISE.format(
            contexto_linhas=_build_contexto(card_context, plataforma_hint),
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

        for attempt in range(3):
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    GROQ_API_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                )
            if resp.status_code == 429 and attempt < 2:
                await asyncio.sleep(20 * (attempt + 1))
                continue
            resp.raise_for_status()
            break
        data = resp.json()

        raw_text = data["choices"][0]["message"]["content"].strip()
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        result = json.loads(raw_text)
        result.setdefault("termos_identificados", [])
        result.setdefault("confirmacao_negativacao", False)
        result.setdefault("confianca", 0.5)
        result.setdefault("ocr_raw", "")
        result.setdefault("tipo_acao", "negativacao")
        result.setdefault("tipo_correspondencia", None)
        result.setdefault("nivel_aplicacao", None)
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
        "tipo_acao": "negativacao",
        "tipo_correspondencia": None,
        "nivel_aplicacao": None,
        "data_evidencia": None,
        "confirmacao_negativacao": False,
        "confianca": 0.0,
        "ocr_raw": "",
        "nome_logico": _fallback_nome_logico(card_context, filename),
        "observacoes": f"Erro na análise: {error}",
    }
