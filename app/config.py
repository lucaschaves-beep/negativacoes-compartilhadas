from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    pipefy_token: str
    pipefy_pipe_id: str = "302407449"
    pipefy_api_url: str = "https://api.pipefy.com/graphql"

    groq_api_key: str

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    r2_account_id: str = ""
    r2_access_key: str = ""
    r2_secret_key: str = ""
    r2_bucket: str = "negativacoes-evidencias"
    r2_public_url: str = ""

    app_secret: str = "changeme"
    webhook_secret: str = ""

    # Seções válidas de anexos (ignorar "Anexos Do Email")
    secoes_validas: list[str] = ["Anexos", "N1AP. G. Ads - Print Da Negativação"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
