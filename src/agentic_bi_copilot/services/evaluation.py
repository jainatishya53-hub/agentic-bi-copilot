import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

ChartType: TypeAlias = Literal[
    "line",
    "bar",
    "grouped_bar",
    "table",
]

NormalizedRow: TypeAlias = tuple[str, ...]

TWO_DECIMAL_PLACES = Decimal("0.01")


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


@dataclass(frozen=True, slots=True)
class ResultComparison:
    """Comparison between a reference result and a candidate result."""

    columns_match: bool
    row_count_match: bool
    values_match: bool

    @property
    def is_correct(self) -> bool:
        """Return whether the result values are correct."""

        return self.row_count_match and self.values_match


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


def normalize_number(
    value: float | Decimal,
) -> str:
    """Normalize a number to two decimal places."""

    normalized_value = Decimal(str(value)).quantize(
        TWO_DECIMAL_PLACES,
        rounding=ROUND_HALF_UP,
    )

    return f"number:{normalized_value}"


def normalize_value(value: Any) -> str:
    """Convert a result value into a comparable string."""

    if value is None:
        return "null"

    if isinstance(value, bool):
        return f"boolean:{str(value).lower()}"

    if isinstance(value, (int, float, Decimal)):
        return normalize_number(value)

    if isinstance(value, datetime):
        return f"datetime:{value.isoformat()}"

    if isinstance(value, date):
        return f"date:{value.isoformat()}"

    return f"text:{value}"


def normalize_row(
    row: Mapping[str, Any],
    columns: tuple[str, ...],
) -> NormalizedRow:
    """Normalize one result row using a fixed column order."""

    return tuple(normalize_value(row[column]) for column in columns)


def normalize_rows(
    rows: Sequence[Mapping[str, Any]],
    columns: tuple[str, ...],
    compare_row_order: bool,
) -> tuple[NormalizedRow, ...]:
    """Normalize result rows and optionally ignore their order."""

    normalized_rows = tuple(normalize_row(row, columns) for row in rows)

    if compare_row_order:
        return normalized_rows

    return tuple(sorted(normalized_rows))


def compare_query_results(
    reference_columns: Sequence[str],
    reference_rows: Sequence[Mapping[str, Any]],
    candidate_columns: Sequence[str],
    candidate_rows: Sequence[Mapping[str, Any]],
    compare_row_order: bool = False,
) -> ResultComparison:
    """Compare a candidate query result with a reference result."""

    reference_column_names = tuple(reference_columns)
    candidate_column_names = tuple(candidate_columns)

    columns_match = reference_column_names == candidate_column_names
    column_count_match = len(reference_column_names) == len(candidate_column_names)
    row_count_match = len(reference_rows) == len(candidate_rows)

    if not column_count_match or not row_count_match:
        return ResultComparison(
            columns_match=columns_match,
            row_count_match=row_count_match,
            values_match=False,
        )

    reference_values = normalize_rows(
        reference_rows,
        reference_column_names,
        compare_row_order,
    )
    candidate_values = normalize_rows(
        candidate_rows,
        candidate_column_names,
        compare_row_order,
    )

    values_match = reference_values == candidate_values

    return ResultComparison(
        columns_match=columns_match,
        row_count_match=row_count_match,
        values_match=values_match,
    )
