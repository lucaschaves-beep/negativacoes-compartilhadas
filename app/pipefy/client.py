import httpx
from typing import Optional
from app.config import get_settings

settings = get_settings()

QUERY_GET_CARD = """
query GetCard($cardId: ID!) {
  card(id: $cardId) {
    id
    title
    current_phase {
      name
    }
    createdAt
    fields {
      name
      value
      array_value
      field {
        id
        label
        type
      }
    }
    attachments {
      url
    }
    comments {
      text
      created_at
    }
  }
}
"""

QUERY_LIST_CARDS = """
query ListCards($pipeId: ID!, $after: String) {
  cards(pipe_id: $pipeId, first: 50, after: $after) {
    edges {
      node {
        id
        title
        current_phase { name }
        createdAt
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

QUERY_PHASE_CARDS = """
query PhaseCards($phaseId: ID!, $after: String) {
  phase(id: $phaseId) {
    cards_count
    cards(first: 50, after: $after) {
      edges {
        node {
          id
          title
          fields {
            name
            value
            array_value
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""


class PipefyClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.pipefy_token}",
            "Content-Type": "application/json",
        }

    async def _query(self, query: str, variables: dict) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                settings.pipefy_api_url,
                json={"query": query, "variables": variables},
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                raise ValueError(f"Pipefy GraphQL error: {data['errors']}")
            return data["data"]

    async def get_card(self, card_id: str) -> dict:
        data = await self._query(QUERY_GET_CARD, {"cardId": card_id})
        return data["card"]

    async def list_all_cards(self) -> list[dict]:
        cards = []
        cursor = None

        while True:
            variables = {"pipeId": settings.pipefy_pipe_id}
            if cursor:
                variables["after"] = cursor

            data = await self._query(QUERY_LIST_CARDS, variables)
            page = data["cards"]

            for edge in page["edges"]:
                cards.append(edge["node"])

            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]

        return cards

    async def list_phase_cards_page(self, phase_id: str, cursor: str | None = None) -> dict:
        """Retorna uma página de 50 cards de uma fase, com campos, para filtragem."""
        variables: dict = {"phaseId": phase_id}
        if cursor:
            variables["after"] = cursor
        data = await self._query(QUERY_PHASE_CARDS, variables)
        phase = data["phase"]
        return {
            "cards": [edge["node"] for edge in phase["cards"]["edges"]],
            "has_next": phase["cards"]["pageInfo"]["hasNextPage"],
            "next_cursor": phase["cards"]["pageInfo"]["endCursor"],
            "total": phase.get("cards_count", 0),
        }

    async def download_attachment(self, url: str) -> bytes:
        # Pipefy retorna caminhos relativos — converte para URL completa
        if url and not url.startswith("http"):
            url = f"https://app.pipefy.com/{url.lstrip('/')}"

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.content
