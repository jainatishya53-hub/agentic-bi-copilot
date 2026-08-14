from pathlib import Path

import pytest

from agentic_bi_copilot.security.sql_validator import validate_sql


def test_accepts_simple_select() -> None:
    result = validate_sql(
        "SELECT product_id, name FROM products LIMIT 20"
    )

    assert result.is_safe
    assert result.errors == ()
    assert result.referenced_tables == ("products",)
    assert result.normalized_sql is not None


def test_accepts_reference_query_with_ctes() -> None:
    reference_query_path = (
        Path(__file__).parents[1]
        / "evaluation"
        / "regional_revenue_last_six_months.sql"
    )
    sql = reference_query_path.read_text(encoding="utf-8")

    result = validate_sql(sql)

    assert result.is_safe
    assert result.referenced_tables == (
        "customers",
        "order_items",
        "orders",
        "regions",
    )


@pytest.mark.parametrize(
    ("sql", "expected_error"),
    [
        ("", "empty_query"),
        ("SELECT * FROM (", "parse_error"),
        (
            "SELECT * FROM products LIMIT 10; DELETE FROM products",
            "multiple_statements",
        ),
        ("DROP TABLE products", "non_select_statement"),
        (
            """
            WITH deleted AS (
                DELETE FROM products
                RETURNING *
            )
            SELECT * FROM deleted
            LIMIT 10
            """,
            "prohibited_operation: delete",
        ),
        (
            "SELECT * FROM pg_catalog.pg_tables LIMIT 10",
            "unauthorized_schema: pg_catalog",
        ),
        (
            "SELECT * FROM secret_table LIMIT 10",
            "unauthorized_table: secret_table",
        ),
        ("SELECT * FROM products", "missing_limit"),
        (
            "SELECT * FROM products LIMIT 501",
            "limit_exceeds_500",
        ),
        ("SELECT pg_sleep(1) LIMIT 1", "prohibited_function: pg_sleep"),
    ],
)
def test_rejects_unsafe_sql(
    sql: str,
    expected_error: str,
) -> None:
    result = validate_sql(sql)

    assert not result.is_safe
    assert result.normalized_sql is None
    assert any(
        error.startswith(expected_error)
        for error in result.errors
    )