from pathlib import Path

import pytest

from agentic_bi_copilot.database.query_service import (
    execute_readonly_query,
)
from agentic_bi_copilot.security.sql_validator import validate_sql
from agentic_bi_copilot.services.evaluation import (
    EvaluationCase,
    get_reference_sql_path,
    load_evaluation_cases,
)

CASES_PATH = Path(__file__).parents[1] / "evaluation" / "cases.json"

EVALUATION_CASES = load_evaluation_cases(CASES_PATH)


def evaluation_case_id(
    case: EvaluationCase,
) -> str:
    return case.key


def test_evaluation_dataset_contains_twelve_cases() -> None:
    assert len(EVALUATION_CASES) == 12


@pytest.mark.parametrize(
    "case",
    EVALUATION_CASES,
    ids=evaluation_case_id,
)
def test_reference_query_is_safe_and_returns_expected_result(
    case: EvaluationCase,
) -> None:
    sql_path = get_reference_sql_path(
        case,
        CASES_PATH,
    )

    assert sql_path.is_file(), f"Reference SQL file does not exist: {sql_path}"

    sql = sql_path.read_text(encoding="utf-8")
    validation = validate_sql(sql)

    assert validation.is_safe, validation.errors
    assert validation.normalized_sql is not None

    result = execute_readonly_query(validation.normalized_sql)

    assert tuple(result.columns) == case.expected_columns
    assert result.row_count > 0
