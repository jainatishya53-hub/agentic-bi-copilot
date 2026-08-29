import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentic_bi_copilot.services.evaluation import (
    EvaluationCase,
)
from agentic_bi_copilot.services.evaluation_report import (
    build_evaluation_report,
    select_evaluation_cases,
    write_evaluation_report,
)
from agentic_bi_copilot.services.evaluation_suite import (
    EvaluationCaseOutcome,
    EvaluationSuiteResult,
)


def create_case(key: str) -> EvaluationCase:
    return EvaluationCase(
        key=key,
        question=(f"Show the evaluation result for {key}."),
        expected_tables=("orders",),
        expected_columns=("revenue",),
        expected_chart_type="bar",
        reference_sql_file=f"{key}.sql",
    )


def create_suite_result() -> EvaluationSuiteResult:
    return EvaluationSuiteResult(
        total_cases=2,
        correct_cases=1,
        result_accuracy_pct=50.0,
        chart_type_matches=1,
        p95_processing_time_ms=2500.0,
        outcomes=(
            EvaluationCaseOutcome(
                case_key="case_1",
                is_correct=True,
                chart_type_match=True,
                processing_time_ms=1500.0,
                generated_sql="SELECT 1 LIMIT 500;",
                error=None,
            ),
            EvaluationCaseOutcome(
                case_key="case_2",
                is_correct=False,
                chart_type_match=False,
                processing_time_ms=2500.0,
                generated_sql="SELECT 2 LIMIT 500;",
                error=None,
            ),
        ),
    )


def test_selects_one_evaluation_case() -> None:
    cases = (
        create_case("case_1"),
        create_case("case_2"),
    )

    selected_cases = select_evaluation_cases(
        cases,
        "case_2",
    )

    assert selected_cases == (cases[1],)

    with pytest.raises(
        ValueError,
        match="Unknown evaluation case",
    ):
        select_evaluation_cases(
            cases,
            "missing_case",
        )


def test_builds_evaluation_report() -> None:
    generated_at = datetime(
        2026,
        8,
        29,
        12,
        0,
        tzinfo=UTC,
    )

    report = build_evaluation_report(
        create_suite_result(),
        generated_at,
    )

    assert report["generated_at"] == ("2026-08-29T12:00:00+00:00")
    assert report["metrics"] == {
        "total_cases": 2,
        "correct_cases": 1,
        "failed_cases": 0,
        "result_accuracy_pct": 50.0,
        "chart_type_matches": 1,
        "p95_processing_time_ms": 2500.0,
    }
    assert len(report["outcomes"]) == 2


def test_writes_evaluation_report(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "reports" / "evaluation.json"
    report = build_evaluation_report(create_suite_result())

    write_evaluation_report(
        report,
        output_path,
    )

    saved_report = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.is_file()
    assert saved_report["metrics"]["result_accuracy_pct"] == 50.0
