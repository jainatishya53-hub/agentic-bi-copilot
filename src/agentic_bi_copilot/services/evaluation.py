import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChartType = Literal[
    "line",
    "bar",
    "grouped_bar",
    "table",
]


class EvaluationCase(BaseModel):
    """Expected information for one analytics evaluation question."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9_]+$",
    )
    question: str = Field(
        min_length=10,
        max_length=500,
    )
    expected_tables: tuple[str, ...] = Field(min_length=1)
    expected_columns: tuple[str, ...] = Field(min_length=1)
    expected_chart_type: ChartType
    reference_sql_file: str = Field(min_length=1)
    compare_row_order: bool = False


def read_evaluation_data(path: Path) -> object:
    """Read the raw JSON value from an evaluation file."""

    return json.loads(path.read_text(encoding="utf-8"))


def validate_case_list(raw_data: object) -> list[object]:
    """Make sure the evaluation file contains a non-empty list."""

    if not isinstance(raw_data, list):
        raise TypeError("Evaluation data must be a list.")

    if not raw_data:
        raise ValueError("Evaluation data cannot be empty.")

    return raw_data


def check_unique_keys(
    cases: tuple[EvaluationCase, ...],
) -> None:
    """Make sure every evaluation case has a different key."""

    keys = [case.key for case in cases]

    if len(keys) != len(set(keys)):
        raise ValueError("Evaluation case keys must be unique.")


def load_evaluation_cases(
    path: Path,
) -> tuple[EvaluationCase, ...]:
    """Load and validate evaluation cases from a JSON file."""

    raw_data = read_evaluation_data(path)
    raw_cases = validate_case_list(raw_data)

    cases = tuple(EvaluationCase.model_validate(raw_case) for raw_case in raw_cases)

    check_unique_keys(cases)

    return cases


def get_reference_sql_path(
    case: EvaluationCase,
    cases_path: Path,
) -> Path:
    """Return the SQL file path for an evaluation case."""

    return cases_path.parent / case.reference_sql_file
