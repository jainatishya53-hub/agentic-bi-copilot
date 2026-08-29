import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from agentic_bi_copilot.security.sql_validator import (
    validate_sql,
)

DEFAULT_CASES_PATH = Path("tests/evaluation/unsafe_queries.json")
DEFAULT_REPORT_PATH = Path("artifacts/safety_evaluation_report.json")

PERCENT_SCALE = 100


class UnsafeQueryCase(BaseModel):
    """Describe one unsafe SQL evaluation case."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9_]+$",
    )
    category: str = Field(min_length=1)
    sql: str
    expected_error: str = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class SafetyEvaluationOutcome:
    """Store the result of one unsafe SQL evaluation."""

    case_key: str
    category: str
    blocked: bool
    reason_matches: bool
    passed: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SafetyEvaluationMetrics:
    """Store aggregate SQL safety metrics."""

    total_queries: int
    blocked_queries: int
    blocking_rate_pct: float
    expected_reason_matches: int
    failed_cases: int


@dataclass(frozen=True, slots=True)
class SafetyEvaluationReport:
    """Store the complete SQL safety evaluation report."""

    metrics: SafetyEvaluationMetrics
    outcomes: tuple[SafetyEvaluationOutcome, ...]

    def to_dict(self) -> dict[str, object]:
        """Convert the report into JSON-serializable data."""

        return {
            "metrics": asdict(self.metrics),
            "outcomes": [asdict(outcome) for outcome in self.outcomes],
        }


def load_unsafe_query_cases(
    path: Path,
) -> tuple[UnsafeQueryCase, ...]:
    """Load and validate unsafe SQL cases from JSON."""

    raw_data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw_data, list):
        raise TypeError("Unsafe query evaluation data must be a list.")

    if not raw_data:
        raise ValueError("Unsafe query evaluation data cannot be empty.")

    cases = tuple(UnsafeQueryCase.model_validate(raw_case) for raw_case in raw_data)

    keys = [case.key for case in cases]

    if len(keys) != len(set(keys)):
        raise ValueError("Unsafe query evaluation keys must be unique.")

    return cases


def run_safety_evaluation(
    cases: tuple[UnsafeQueryCase, ...],
) -> SafetyEvaluationReport:
    """Run all unsafe SQL cases through the validator."""

    if not cases:
        raise ValueError("Safety evaluation requires at least one case.")

    outcomes: list[SafetyEvaluationOutcome] = []

    for case in cases:
        validation = validate_sql(case.sql)

        blocked = not validation.is_safe
        reason_matches = any(
            error.startswith(case.expected_error) for error in validation.errors
        )
        passed = blocked and reason_matches

        outcomes.append(
            SafetyEvaluationOutcome(
                case_key=case.key,
                category=case.category,
                blocked=blocked,
                reason_matches=reason_matches,
                passed=passed,
                errors=validation.errors,
            )
        )

    total_queries = len(outcomes)
    blocked_queries = sum(outcome.blocked for outcome in outcomes)
    expected_reason_matches = sum(outcome.reason_matches for outcome in outcomes)
    failed_cases = sum(not outcome.passed for outcome in outcomes)

    blocking_rate_pct = round(
        blocked_queries / total_queries * PERCENT_SCALE,
        2,
    )

    metrics = SafetyEvaluationMetrics(
        total_queries=total_queries,
        blocked_queries=blocked_queries,
        blocking_rate_pct=blocking_rate_pct,
        expected_reason_matches=(expected_reason_matches),
        failed_cases=failed_cases,
    )

    return SafetyEvaluationReport(
        metrics=metrics,
        outcomes=tuple(outcomes),
    )


def write_safety_evaluation_report(
    report: SafetyEvaluationReport,
    output_path: Path,
) -> None:
    """Write the safety report as formatted JSON."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            report.to_dict(),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Build command-line arguments for the benchmark."""

    parser = argparse.ArgumentParser(
        description=("Measure the SQL validator's unsafe-query blocking rate.")
    )

    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help="Path to the unsafe-query JSON dataset.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path where the JSON report will be written.",
    )

    return parser


def main() -> None:
    """Run the SQL safety benchmark from the command line."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    cases = load_unsafe_query_cases(arguments.cases)
    report = run_safety_evaluation(cases)

    write_safety_evaluation_report(
        report,
        arguments.output,
    )

    metrics = report.metrics

    print(
        "Unsafe-query blocking rate:",
        f"{metrics.blocking_rate_pct:.2f}%",
        f"({metrics.blocked_queries}/{metrics.total_queries})",
    )
    print(
        "Expected rejection reasons:",
        f"{metrics.expected_reason_matches}/{metrics.total_queries}",
    )
    print("Failed cases:", metrics.failed_cases)
    print("Report written to:", arguments.output)

    if metrics.failed_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
