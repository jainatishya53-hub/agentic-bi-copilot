from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from agentic_bi_copilot.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create and reuse the application's database engine."""
    settings = get_settings()

    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


@contextmanager
def database_connection() -> Iterator[Connection]:
    """Provide a database connection and close it after use."""
    with get_engine().connect() as connection:
        yield connection
