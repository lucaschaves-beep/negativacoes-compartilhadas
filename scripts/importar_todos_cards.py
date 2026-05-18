"""
Script para importação inicial de todos os cards históricos do Pipefy.
Execute uma vez para popular a base com o histórico completo.

Uso:
    python scripts/importar_todos_cards.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipefy.client import PipefyClient
from app.workers.tasks import process_card


async def main():
    print("Buscando todos os cards do Pipefy...")
    pipefy = PipefyClient()
    cards = await pipefy.list_all_cards()
    print(f"Total de cards encontrados: {len(cards)}")

    for i, card in enumerate(cards, 1):
        card_id = card["id"]
        print(f"[{i}/{len(cards)}] Enfileirando card {card_id} - {card.get('title', '')}")
        process_card.delay(card_id)

    print(f"\nPronto! {len(cards)} cards enfileirados para processamento.")
    print("Acompanhe o progresso em http://localhost:5555 (Flower)")


if __name__ == "__main__":
    asyncio.run(main())
