from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from pathlib import Path

from agentic_bi_copilot.services.evaluation import (
    EvaluationCase,
)
from agentic_bi_copilot.services.evaluation_runner import (
    run_evaluation_case,
)

PERCENT_SCALE = 100


@dataclass(frozen=True, slots=True)
class EvaluationCaseOutcome:
    """Serializable outcome for one evaluation case."""

    case_key: str
    is_correct: bool
    chart_type_match: bool
    processing_time_ms: float | None
    generated_sql: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class EvaluationSuiteResult:
    """Summary of a complete evaluation run."""

    total_cases: int
    correct_cases: int
    result_accuracy_pct: float
    chart_type_matches: int
    p95_processing_time_ms: float | None
    outcomes: tuple[EvaluationCaseOutcome, ...]

    @property
    def failed_cases(self) -> int:
        """Return the number of cases that raised an error."""

        return sum(outcome.error is not None for outcome in self.outcomes)


def calculate_nearest_rank_percentile(
    values: Sequence[float],
    percentile: float,
) -> float:
    """Calculate a percentile using the nearest-rank method."""

    if not values:
        raise ValueError("Cannot calculate a percentile without values.")

    if percentile <= 0 or percentile > PERCENT_SCALE:
        raise ValueError("Percentile must be greater than 0 and at most 100.")

    ordered_values = sorted(values)
    rank = ceil(len(ordered_values) * percentile / PERCENT_SCALE)
    index = max(rank - 1, 0)

    return round(ordered_values[index], 2)


def build_suite_result(
    outcomes: Sequence[EvaluationCaseOutcome],
) -> EvaluationSuiteResult:
    """Build aggregate metrics from case outcomes."""

    if not outcomes:
        raise ValueError("Cannot build an evaluation result without outcomes.")

    total_cases = len(outcomes)
    correct_cases = sum(outcome.is_correct for outcome in outcomes)
    chart_type_matches = sum(outcome.chart_type_match for outcome in outcomes)
    processing_times = [
        outcome.processing_time_ms
        for outcome in outcomes
        if outcome.processing_time_ms is not None
    ]

    if processing_times:
        p95_processing_time_ms = calculate_nearest_rank_percentile(
            processing_times,
            95,
        )
    else:
        p95_processing_time_ms = None

    result_accuracy_pct = round(
        correct_cases / total_cases * PERCENT_SCALE,
        2,
    )

    return EvaluationSuiteResult(
        total_cases=total_cases,
        correct_cases=correct_cases,
        result_accuracy_pct=result_accuracy_pct,
        chart_type_matches=chart_type_matches,
        p95_processing_time_ms=p95_processing_time_ms,
        outcomes=tuple(outcomes),
    )


def run_evaluation_suite(
    cases: Sequence[EvaluationCase],
    cases_path: Path,
) -> EvaluationSuiteResult:
    """Run all evaluation cases and calculate aggregate metrics."""

    if not cases:
        raise ValueError("Evaluation suite requires at least one case.")

    outcomes: list[EvaluationCaseOutcome] = []

    for case in cases:
        try:
            result = run_evaluation_case(
                case,
                cases_path,
            )
        except Exception as exc:  # noqa: BLE001
            outcomes.append(
                EvaluationCaseOutcome(
                    case_key=case.key,
                    is_correct=False,
                    chart_type_match=False,
                    processing_time_ms=None,
                    generated_sql=None,
                    error=(f"{type(exc).__name__}: {exc}"),
                )
            )
            continue

        outcomes.append(
            EvaluationCaseOutcome(
                case_key=case.key,
                is_correct=result.is_correct,
                chart_type_match=(result.chart_type_match),
                processing_time_ms=(result.processing_time_ms),
                generated_sql=result.generated_sql,
                error=None,
            )
        )

    return build_suite_result(outcomes)
