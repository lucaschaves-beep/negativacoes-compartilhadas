"""
Registra o webhook do Pipefy apontando para a URL pública da sua API.

Uso:
    python scripts/configurar_webhook.py --url https://minha-api.railway.app

O Pipefy enviará eventos automaticamente quando cards forem criados ou atualizados.
"""
import asyncio
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.config import get_settings

settings = get_settings()

CREATE_WEBHOOK = """
mutation CreateWebhook($pipeId: ID!, $url: String!, $actions: [String]!) {
  createWebhook(input: {
    pipe_id: $pipeId
    url: $url
    actions: $actions
    headers: "{}"
  }) {
    webhook {
      id
      name
      url
      actions
    }
  }
}
"""

LIST_WEBHOOKS = """
query ListWebhooks($pipeId: ID!) {
  pipe(id: $pipeId) {
    webhooks {
      id
      name
      url
      actions
    }
  }
}
"""

DELETE_WEBHOOK = """
mutation DeleteWebhook($id: ID!) {
  deleteWebhook(input: { id: $id }) {
    success
  }
}
"""


async def list_webhooks():
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            settings.pipefy_api_url,
            json={"query": LIST_WEBHOOKS, "variables": {"pipeId": settings.pipefy_pipe_id}},
            headers={"Authorization": f"Bearer {settings.pipefy_token}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        return data["data"]["pipe"]["webhooks"]


async def create_webhook(url: str):
    webhook_url = f"{url.rstrip('/')}/webhook/pipefy"
    actions = ["card.create", "card.update", "card.move"]

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            settings.pipefy_api_url,
            json={
                "query": CREATE_WEBHOOK,
                "variables": {
                    "pipeId": settings.pipefy_pipe_id,
                    "url": webhook_url,
                    "actions": actions,
                },
            },
            headers={"Authorization": f"Bearer {settings.pipefy_token}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise ValueError(data["errors"])
        return data["data"]["createWebhook"]["webhook"]


async def delete_webhook(webhook_id: str):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            settings.pipefy_api_url,
            json={"query": DELETE_WEBHOOK, "variables": {"id": webhook_id}},
            headers={"Authorization": f"Bearer {settings.pipefy_token}", "Content-Type": "application/json"},
        )
        r.raise_for_status()


async def main(api_url: str | None):
    print(f"\nPipe ID: {settings.pipefy_pipe_id}")

    # Lista webhooks existentes
    webhooks = await list_webhooks()
    if webhooks:
        print(f"\nWebhooks já registrados ({len(webhooks)}):")
        for w in webhooks:
            print(f"  [{w['id']}] {w['url']}  →  {w['actions']}")

        resp = input("\nDeseja remover todos e recriar? (s/N): ").strip().lower()
        if resp == "s":
            for w in webhooks:
                await delete_webhook(w["id"])
                print(f"  Removido: {w['id']}")
    else:
        print("\nNenhum webhook registrado ainda.")

    if not api_url:
        api_url = input("\nDigite a URL pública da sua API (ex: https://minha-api.railway.app): ").strip()

    if not api_url:
        print("URL não fornecida. Saindo.")
        return

    webhook = await create_webhook(api_url)
    print(f"\nWebhook criado com sucesso!")
    print(f"  ID:      {webhook['id']}")
    print(f"  URL:     {webhook['url']}")
    print(f"  Eventos: {webhook['actions']}")
    print(f"\nO Pipefy enviará eventos automaticamente para a sua API.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="URL pública da API", default=None)
    args = parser.parse_args()
    asyncio.run(main(args.url))
