"""
Verifica se todos os serviços estão funcionando corretamente.

Uso:
    python scripts/health_check.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check(label: str, ok: bool, detalhe: str = ""):
    status = "✅" if ok else "❌"
    linha = f"  {status} {label}"
    if detalhe:
        linha += f"  → {detalhe}"
    print(linha)
    return ok


async def main():
    print("\n" + "=" * 50)
    print("  Health Check — Negativações Compartilhadas")
    print("=" * 50 + "\n")

    resultados = []

    # 1. Variáveis de ambiente
    try:
        from app.config import get_settings
        s = get_settings()
        resultados.append(check(".env carregado", True))
        resultados.append(check("PIPEFY_TOKEN", bool(s.pipefy_token), s.pipefy_token[:8] + "..."))
        resultados.append(check("GEMINI_API_KEY", bool(s.gemini_api_key), s.gemini_api_key[:8] + "..."))
        resultados.append(check("DATABASE_URL", bool(s.database_url)))
        resultados.append(check("REDIS_URL", bool(s.redis_url), s.redis_url))
    except Exception as e:
        resultados.append(check(".env carregado", False, str(e)))

    print()

    # 2. Banco de dados
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from app.config import get_settings
        s = get_settings()
        db_url = s.database_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(db_url)
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        await engine.dispose()
        resultados.append(check("Banco de dados (Supabase)", True))
    except Exception as e:
        resultados.append(check("Banco de dados (Supabase)", False, str(e)[:80]))

    print()

    # 3. Redis
    try:
        import redis
        from app.config import get_settings
        s = get_settings()
        r = redis.from_url(s.redis_url)
        r.ping()
        resultados.append(check("Redis", True))
    except Exception as e:
        resultados.append(check("Redis", False, str(e)[:60]))

    print()

    # 4. Gemini API
    try:
        import google.generativeai as genai
        from app.config import get_settings
        s = get_settings()
        genai.configure(api_key=s.gemini_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content("responda apenas: ok")
        resultados.append(check("Gemini 1.5 Flash", "ok" in resp.text.lower(), resp.text.strip()[:30]))
    except Exception as e:
        resultados.append(check("Gemini 1.5 Flash", False, str(e)[:80]))

    print()

    # 5. Pipefy API
    try:
        from app.pipefy.client import PipefyClient
        pipefy = PipefyClient()
        cards = await pipefy.list_all_cards()
        resultados.append(check("Pipefy API", True, f"{len(cards)} cards encontrados no pipe"))
    except Exception as e:
        resultados.append(check("Pipefy API", False, str(e)[:80]))

    print()

    # 6. sentence-transformers
    try:
        from app.ai.embeddings import generate_embedding
        emb = generate_embedding("teste de embedding")
        resultados.append(check("sentence-transformers", len(emb) == 384, f"{len(emb)} dimensões"))
    except Exception as e:
        resultados.append(check("sentence-transformers", False, str(e)[:80]))

    print()

    # Resumo
    total = len(resultados)
    ok = sum(resultados)
    print("─" * 50)
    if ok == total:
        print(f"  ✅ Tudo funcionando! ({ok}/{total})")
    else:
        print(f"  ⚠️  {ok}/{total} serviços OK — verifique os itens com ❌")
    print()


if __name__ == "__main__":
    asyncio.run(main())
