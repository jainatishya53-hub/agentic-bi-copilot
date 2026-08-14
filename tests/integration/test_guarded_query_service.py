import pytest

from agentic_bi_copilot.database.query_service import (
    UnsafeQueryError,
    execute_validated_query,
)


def test_validated_query_executes_safe_sql() -> None:
    result = execute_validated_query(
        """
        SELECT region_id, name
        FROM regions
        ORDER BY region_id
        LIMIT 10
        """
    )

    assert result.validation.is_safe
    assert result.validation.referenced_tables == ("regions",)
    assert result.query_result.row_count == 4
    assert result.query_result.columns == ["region_id", "name"]


def test_validated_query_rejects_write_sql() -> None:
    with pytest.raises(UnsafeQueryError) as captured_error:
        execute_validated_query(
            "DELETE FROM products WHERE product_id = 1"
        )

    validation = captured_error.value.validation

    assert not validation.is_safe
    assert "non_select_statement" in validation.errors


def test_validated_query_rejects_missing_limit() -> None:
    with pytest.raises(UnsafeQueryError) as captured_error:
        execute_validated_query("SELECT * FROM products")

    validation = captured_error.value.validation

    assert not validation.is_safe
    assert "missing_limit" in validation.errors