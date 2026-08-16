from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy import text

from agentic_bi_copilot.config import get_settings
from agentic_bi_copilot.database.connection import database_connection
from agentic_bi_copilot.security.sql_validator import (
    SQLValidationResult,
    validate_sql,
)


class ResultLimitExceededError(RuntimeError):
    """Raised when a query returns more rows than allowed."""


class UnsafeQueryError(ValueError):
    """Raised when SQL fails the safety checks."""

    def __init__(self, validation: SQLValidationResult) -> None:
        self.validation = validation

        message = "Unsafe SQL: " + ", ".join(validation.errors)
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Store the data returned by a database query."""

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float


@dataclass(frozen=True, slots=True)
class ValidatedQueryResult:
    """Store both the safety result and the database result."""

    validation: SQLValidationResult
    query_result: QueryResult


def _run_readonly_query(
    sql: str,
    statement_timeout_ms: int,
    fetch_limit: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Run SQL inside a read-only database transaction."""
    with database_connection() as connection, connection.begin():
        connection.execute(text("SET TRANSACTION READ ONLY"))

        # Stop queries that take longer than the configured time.
        connection.execute(
            text(f"SET LOCAL statement_timeout = '{statement_timeout_ms}ms'")
        )

        result = connection.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(row) for row in result.mappings().fetchmany(fetch_limit)]

    return columns, rows


def _check_result_limit(
    rows: list[dict[str, Any]],
    max_result_rows: int,
) -> None:
    """Raise an error when a query returns too many rows."""
    if len(rows) > max_result_rows:
        raise ResultLimitExceededError(
            f"Query returned more than {max_result_rows} rows."
        )


def execute_readonly_query(sql: str) -> QueryResult:
    """Execute SQL with database and application safety limits."""
    settings = get_settings()
    started_at = perf_counter()

    # Fetch one extra row so we can detect an oversized result.
    columns, rows = _run_readonly_query(
        sql=sql,
        statement_timeout_ms=settings.sql_statement_timeout_ms,
        fetch_limit=settings.max_result_rows + 1,
    )

    _check_result_limit(
        rows=rows,
        max_result_rows=settings.max_result_rows,
    )

    execution_time_ms = round(
        (perf_counter() - started_at) * 1000,
        2,
    )

    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        execution_time_ms=execution_time_ms,
    )


def execute_validated_query(sql: str) -> ValidatedQueryResult:
    """Validate SQL before sending it to the database."""
    validation = validate_sql(sql)

    if not validation.is_safe or validation.normalized_sql is None:
        raise UnsafeQueryError(validation)

    query_result = execute_readonly_query(validation.normalized_sql)

    return ValidatedQueryResult(
        validation=validation,
        query_result=query_result,
    )
