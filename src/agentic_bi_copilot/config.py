from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"

    database_url: str = (
        "postgresql+psycopg://bi_reader:change-me@localhost:5432/bi_copilot"
    )
    api_base_url: str = "http://127.0.0.1:8000"

    openai_api_key: str = ""
    model_name: str = ""

    langsmith_tracing: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "agentic-bi-copilot"

    max_result_rows: int = 500
    sql_statement_timeout_ms: int = 5000
    data_as_of_date: date = date(2026, 7, 31)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()