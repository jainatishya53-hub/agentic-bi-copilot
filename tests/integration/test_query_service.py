from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.exc import DBAPIError

from agentic_bi_copilot.database.query_service import (
    ResultLimitExceededError,
    execute_readonly_query,
)


def test_executes_small_read_query() -> None:
    result = execute_readonly_query(
        "SELECT region_id, name FROM regions ORDER BY region_id LIMIT 10"
    )

    assert result.columns == ["region_id", "name"]
    assert result.row_count == 4
    assert [row["name"] for row in result.rows] == [
        "North",
        "South",
        "East",
        "West",
    ]
    assert result.execution_time_ms >= 0


def test_reference_revenue_query() -> None:
    reference_query_path = (
        Path(__file__).parents[1]
        / "evaluation"
        / "regional_revenue_last_six_months.sql"
    )
    sql = reference_query_path.read_text(encoding="utf-8")

    result = execute_readonly_query(sql)

    anomalies = {
        (row["region"], row["month"])
        for row in result.rows
        if row["unusual_decline"]
    }

    assert result.row_count == 24
    assert anomalies == {
        ("West", date(2026, 3, 1)),
        ("South", date(2026, 5, 1)),
        ("West", date(2026, 7, 1)),
    }


def test_rejects_results_above_row_limit() -> None:
    with pytest.raises(ResultLimitExceededError):
        execute_readonly_query(
            "SELECT value FROM generate_series(1, 501) AS value"
        )


def test_database_blocks_write_query() -> None:
    with pytest.raises(DBAPIError):
        execute_readonly_query(
            "CREATE TABLE forbidden_test_table(id integer)"
        )