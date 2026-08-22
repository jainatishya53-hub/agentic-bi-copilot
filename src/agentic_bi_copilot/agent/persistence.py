from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agentic_bi_copilot.config import get_settings


@lru_cache
def get_checkpoint_pool() -> ConnectionPool:
    """Create and reuse the checkpoint database connection pool."""

    settings = get_settings()

    return ConnectionPool(
        conninfo=settings.checkpoint_database_url,
        min_size=settings.checkpoint_pool_min_size,
        max_size=settings.checkpoint_pool_max_size,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=True,
    )


@lru_cache
def get_postgres_checkpointer() -> PostgresSaver:
    """Create and reuse the LangGraph PostgreSQL checkpointer."""

    pool = get_checkpoint_pool()
    return PostgresSaver(pool)


def setup_checkpoint_database() -> None:
    """Create the LangGraph checkpoint tables when needed."""

    checkpointer = get_postgres_checkpointer()
    checkpointer.setup()


def close_checkpoint_pool() -> None:
    """Close checkpoint database connections during application shutdown."""

    if get_checkpoint_pool.cache_info().currsize == 0:
        return

    pool = get_checkpoint_pool()
    pool.close()

    get_postgres_checkpointer.cache_clear()
    get_checkpoint_pool.cache_clear()
