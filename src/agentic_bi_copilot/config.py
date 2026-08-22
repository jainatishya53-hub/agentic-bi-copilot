from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # General application settings.
    app_env: str = "development"
    api_base_url: str = "http://127.0.0.1:8000"

    # Read-only connection used for business queries.
    database_url: str = (
        "postgresql+psycopg://bi_reader:change-me@localhost:5432/bi_copilot"
    )

    # Writable connection used only for LangGraph checkpoints.
    checkpoint_database_url: str = (
        "postgresql://bi_agent:change-me@localhost:5432/bi_copilot"
    )
    checkpoint_pool_min_size: int = 1
    checkpoint_pool_max_size: int = 5

    # Language model settings.
    openai_api_key: str = ""
    model_name: str = ""

    # LangSmith tracing settings.
    langsmith_tracing: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "agentic-bi-copilot"

    # Query safety settings.
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
    """Return one shared settings object."""

    return Settings()
