"""
Setup guiado: gera o arquivo .env com todas as configurações necessárias.

Uso:
    python scripts/setup.py
"""
import os
import sys
import secrets

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def perguntar(label: str, default: str = "", obrigatorio: bool = True) -> str:
    sufixo = f" [{default}]" if default else (" (obrigatório)" if obrigatorio else " (opcional, Enter para pular)")
    while True:
        valor = input(f"{label}{sufixo}: ").strip()
        if not valor and default:
            return default
        if not valor and obrigatorio:
            print("  → Campo obrigatório.")
            continue
        return valor


def main():
    print("\n" + "=" * 60)
    print("  SETUP — Negativações Compartilhadas")
    print("=" * 60)

    if os.path.exists(ENV_PATH):
        resp = input(f"\nArquivo .env já existe. Sobrescrever? (s/N): ").strip().lower()
        if resp != "s":
            print("Cancelado.")
            return

    print("\n--- Pipefy ---")
    print("Acesse: https://app.pipefy.com/tokens para gerar seu token.")
    pipefy_token = perguntar("Token do Pipefy (Bearer)")
    pipefy_pipe_id = perguntar("ID do Pipe", default="302407449")

    print("\n--- Google Gemini (gratuito) ---")
    print("Acesse: https://ai.google.dev para obter sua chave gratuita.")
    gemini_key = perguntar("Chave da API Gemini")

    print("\n--- Supabase (gratuito) ---")
    print("Acesse: https://supabase.com → New Project → Settings → Database → Connection string")
    db_url = perguntar("Database URL (postgresql://...)")

    print("\n--- Redis ---")
    redis_url = perguntar("URL do Redis", default="redis://localhost:6379/0")

    print("\n--- Cloudflare R2 (opcional, para cache de imagens) ---")
    print("Pule se não quiser configurar agora (Enter).")
    r2_account = perguntar("R2 Account ID", obrigatorio=False)
    r2_access = perguntar("R2 Access Key", obrigatorio=False)
    r2_secret = perguntar("R2 Secret Key", obrigatorio=False)
    r2_bucket = perguntar("R2 Bucket Name", default="negativacoes-evidencias", obrigatorio=False)
    r2_url = perguntar("R2 Public URL (ex: https://pub-xxx.r2.dev)", obrigatorio=False)

    webhook_secret = secrets.token_hex(32)
    app_secret = secrets.token_hex(32)

    env_content = f"""# Pipefy
PIPEFY_TOKEN={pipefy_token}
PIPEFY_PIPE_ID={pipefy_pipe_id}

# Google Gemini (gratuito)
GEMINI_API_KEY={gemini_key}

# Supabase
DATABASE_URL={db_url}

# Redis
REDIS_URL={redis_url}

# Cloudflare R2 (opcional)
R2_ACCOUNT_ID={r2_account}
R2_ACCESS_KEY={r2_access}
R2_SECRET_KEY={r2_secret}
R2_BUCKET={r2_bucket}
R2_PUBLIC_URL={r2_url}

# Segurança (gerados automaticamente)
APP_SECRET={app_secret}
WEBHOOK_SECRET={webhook_secret}
"""

    with open(ENV_PATH, "w") as f:
        f.write(env_content)

    print(f"\n✅ Arquivo .env criado em: {ENV_PATH}")
    print(f"\nWebhook secret gerado: {webhook_secret}")
    print("  → Configure esse valor no Pipefy ao registrar o webhook.")
    print("\nPróximo passo:")
    print("  1. Execute o banco:  Rode o arquivo migrations/001_init.sql no Supabase")
    print("  2. Suba a API:       docker-compose up")
    print("  3. Teste um card:    python scripts/testar_card.py 741065587")
    print("  4. Configure webhook: python scripts/configurar_webhook.py --url https://sua-api.com")
    print("  5. Importe histórico: python scripts/importar_todos_cards.py")
    print("  6. Interface visual:  streamlit run ui/busca.py")


if __name__ == "__main__":
    main()
