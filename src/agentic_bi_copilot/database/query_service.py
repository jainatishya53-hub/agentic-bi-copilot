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
    pass


class UnsafeQueryError(ValueError):
    def __init__(self, validation: SQLValidationResult) -> None:
        self.validation = validation

        message = "Unsafe SQL: " + ", ".join(validation.errors)
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float


@dataclass(frozen=True, slots=True)
class ValidatedQueryResult:
    validation: SQLValidationResult
    query_result: QueryResult


def execute_readonly_query(sql: str) -> QueryResult:
    settings = get_settings()
    started_at = perf_counter()

    with database_connection() as connection, connection.begin():
        connection.execute(text("SET TRANSACTION READ ONLY"))
        connection.execute(
            text(
                "SET LOCAL statement_timeout = "
                f"'{settings.sql_statement_timeout_ms}ms'"
            )
        )

        result = connection.execute(text(sql))
        columns = list(result.keys())
        rows = [
            dict(row)
            for row in result.mappings().fetchmany(
                settings.max_result_rows + 1
            )
        ]

    if len(rows) > settings.max_result_rows:
        raise ResultLimitExceededError(
            "Query returned more than "
            f"{settings.max_result_rows} rows."
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
    validation = validate_sql(sql)

    if not validation.is_safe or validation.normalized_sql is None:
        raise UnsafeQueryError(validation)

    query_result = execute_readonly_query(validation.normalized_sql)

    return ValidatedQueryResult(
        validation=validation,
        query_result=query_result,
    )