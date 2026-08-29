import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from agentic_bi_copilot.services.evaluation import (
    get_reference_sql_path,
    load_evaluation_cases,
)

VALID_CASE = {
    "key": "top_products",
    "question": "Show the top 10 products by revenue.",
    "expected_tables": [
        "orders",
        "order_items",
        "products",
    ],
    "expected_columns": [
        "product_name",
        "total_revenue",
    ],
    "expected_chart_type": "bar",
    "reference_sql_file": "sql/top_products.sql",
    "compare_row_order": True,
}


def write_json(
    path: Path,
    value: Any,
) -> None:
    """Write test data to a JSON file."""

    path.write_text(
        json.dumps(value),
        encoding="utf-8",
    )


def test_loads_valid_evaluation_cases(
    tmp_path: Path,
) -> None:
    cases_path = tmp_path / "cases.json"
    write_json(cases_path, [VALID_CASE])

    cases = load_evaluation_cases(cases_path)

    assert len(cases) == 1
    assert cases[0].key == "top_products"
    assert cases[0].expected_tables == (
        "orders",
        "order_items",
        "products",
    )
    assert cases[0].expected_chart_type == "bar"
    assert cases[0].compare_row_order is True


def test_rejects_empty_evaluation_file(
    tmp_path: Path,
) -> None:
    cases_path = tmp_path / "cases.json"
    write_json(cases_path, [])

    with pytest.raises(
        ValueError,
        match="Evaluation data cannot be empty",
    ):
        load_evaluation_cases(cases_path)


def test_rejects_duplicate_case_keys(
    tmp_path: Path,
) -> None:
    cases_path = tmp_path / "cases.json"
    write_json(
        cases_path,
        [
            VALID_CASE,
            VALID_CASE,
        ],
    )

    with pytest.raises(
        ValueError,
        match="Evaluation case keys must be unique",
    ):
        load_evaluation_cases(cases_path)


def test_rejects_unknown_chart_type(
    tmp_path: Path,
) -> None:
    cases_path = tmp_path / "cases.json"
    invalid_case = {
        **VALID_CASE,
        "expected_chart_type": "pie",
    }
    write_json(cases_path, [invalid_case])

    with pytest.raises(ValidationError):
        load_evaluation_cases(cases_path)


def test_builds_reference_sql_path(
    tmp_path: Path,
) -> None:
    cases_path = tmp_path / "cases.json"
    write_json(cases_path, [VALID_CASE])

    case = load_evaluation_cases(cases_path)[0]
    sql_path = get_reference_sql_path(
        case,
        cases_path,
    )

    assert sql_path == tmp_path / "sql" / "top_products.sql"
