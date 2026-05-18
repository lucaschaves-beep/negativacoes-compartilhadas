"""
Testa análise de um card específico sem precisar do Celery rodando.

Uso:
    python scripts/testar_card.py 741065587
"""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipefy.client import PipefyClient
from app.pipefy.parser import parse_card_fields, filter_valid_attachments
from app.ai.vision import analyze_image


async def main(card_id: str):
    print(f"Analisando card {card_id}...\n")

    pipefy = PipefyClient()
    card_raw = await pipefy.get_card(card_id)
    parsed = parse_card_fields(card_raw)
    attachments = filter_valid_attachments(card_raw)

    print("=== DADOS DO CARD ===")
    print(f"  Título:       {parsed['titulo']}")
    print(f"  Concorrente:  {parsed.get('concorrente')}")
    print(f"  Cliente MySQL:{parsed.get('cliente_mysql')}")
    print(f"  Plataforma:   {parsed.get('plataforma')}")
    print(f"  Fase:         {parsed.get('fase_atual')}")
    print(f"  Termos:       {parsed.get('termos')}")
    print(f"\n  Anexos válidos encontrados: {len(attachments)}")

    for i, att in enumerate(attachments, 1):
        print(f"\n=== ANEXO {i}: {att['filename']} (seção: {att['secao']}) ===")
        print(f"  Baixando...")
        image_bytes = await pipefy.download_attachment(att["url"])
        print(f"  Tamanho: {len(image_bytes) / 1024:.1f} KB")
        print(f"  Analisando com Gemini Vision...")
        analysis = await analyze_image(image_bytes, parsed, att["filename"])
        print(f"  Nome lógico:      {analysis.get('nome_logico')}")
        print(f"  Marca:            {analysis.get('marca_identificada')}")
        print(f"  Plataforma:       {analysis.get('plataforma')}")
        print(f"  Confirmação:      {analysis.get('confirmacao_negativacao')}")
        print(f"  Confiança:        {analysis.get('confianca')}")
        print(f"  Termos:           {analysis.get('termos_identificados')}")
        print(f"  Tipo:             {analysis.get('tipo_evidencia')}")
        print(f"  Data:             {analysis.get('data_evidencia')}")


if __name__ == "__main__":
    card_id = sys.argv[1] if len(sys.argv) > 1 else "741065587"
    asyncio.run(main(card_id))
