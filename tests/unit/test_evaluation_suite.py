from pathlib import Path

import pytest

from agentic_bi_copilot.services import evaluation_suite
from agentic_bi_copilot.services.evaluation import (
    EvaluationCase,
    ResultComparison,
)
from agentic_bi_copilot.services.evaluation_runner import (
    EvaluationCaseExecutionError,
    EvaluationRunResult,
)
from agentic_bi_copilot.services.evaluation_suite import (
    calculate_nearest_rank_percentile,
    run_evaluation_suite,
)


def create_case(key: str) -> EvaluationCase:
    return EvaluationCase(
        key=key,
        question=(f"Show the revenue result for evaluation {key}."),
        expected_tables=("orders",),
        expected_columns=("revenue",),
        expected_chart_type="bar",
        reference_sql_file=f"{key}.sql",
    )


def test_calculates_nearest_rank_percentile() -> None:
    result = calculate_nearest_rank_percentile(
        [100.0, 200.0, 300.0, 400.0],
        95,
    )

    assert result == 400.0


def test_runs_suite_and_calculates_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = (
        create_case("case_1"),
        create_case("case_2"),
        create_case("case_3"),
        create_case("case_4"),
    )

    case_results = {
        "case_1": (True, True, 100.0),
        "case_2": (False, False, 200.0),
        "case_3": (True, True, 300.0),
    }

    def fake_run_evaluation_case(
        case: EvaluationCase,
        cases_path: Path,
    ) -> EvaluationRunResult:
        assert cases_path == tmp_path / "cases.json"

        if case.key == "case_4":
            raise EvaluationCaseExecutionError("Test evaluation failure.")

        is_correct, chart_match, processing_time = case_results[case.key]

        return EvaluationRunResult(
            case_key=case.key,
            generated_sql="SELECT 1 LIMIT 500;",
            comparison=ResultComparison(
                columns_match=True,
                row_count_match=True,
                values_match=is_correct,
            ),
            chart_type_match=chart_match,
            processing_time_ms=processing_time,
        )

    monkeypatch.setattr(
        evaluation_suite,
        "run_evaluation_case",
        fake_run_evaluation_case,
    )

    result = run_evaluation_suite(
        cases,
        tmp_path / "cases.json",
    )

    assert result.total_cases == 4
    assert result.correct_cases == 2
    assert result.result_accuracy_pct == 50.0
    assert result.chart_type_matches == 2
    assert result.p95_processing_time_ms == 300.0
    assert result.failed_cases == 1
    assert result.outcomes[3].error == (
        "EvaluationCaseExecutionError: Test evaluation failure."
    )


def test_rejects_empty_evaluation_suite(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="requires at least one case",
    ):
        run_evaluation_suite(
            (),
            tmp_path / "cases.json",
        )
