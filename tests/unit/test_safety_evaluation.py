import json
from pathlib import Path

import pytest

from agentic_bi_copilot.services.safety_evaluation import (
    DEFAULT_CASES_PATH,
    UnsafeQueryCase,
    load_unsafe_query_cases,
    run_safety_evaluation,
    write_safety_evaluation_report,
)


def test_loads_twenty_unsafe_query_cases() -> None:
    cases = load_unsafe_query_cases(DEFAULT_CASES_PATH)

    assert len(cases) == 20
    assert len({case.key for case in cases}) == 20


def test_blocks_all_unsafe_query_cases() -> None:
    cases = load_unsafe_query_cases(DEFAULT_CASES_PATH)

    report = run_safety_evaluation(cases)

    assert report.metrics.total_queries == 20
    assert report.metrics.blocked_queries == 20
    assert report.metrics.blocking_rate_pct == 100.0
    assert report.metrics.expected_reason_matches == 20
    assert report.metrics.failed_cases == 0
    assert all(outcome.passed for outcome in report.outcomes)


def test_records_unblocked_query_as_failure() -> None:
    case = UnsafeQueryCase(
        key="unexpected_safe_query",
        category="test",
        sql="SELECT * FROM products LIMIT 10",
        expected_error="missing_limit",
    )

    report = run_safety_evaluation((case,))
    outcome = report.outcomes[0]

    assert outcome.blocked is False
    assert outcome.reason_matches is False
    assert outcome.passed is False
    assert report.metrics.blocked_queries == 0
    assert report.metrics.blocking_rate_pct == 0.0
    assert report.metrics.failed_cases == 1


def test_rejects_empty_safety_evaluation() -> None:
    with pytest.raises(
        ValueError,
        match="at least one case",
    ):
        run_safety_evaluation(())


def test_writes_safety_evaluation_report(
    tmp_path: Path,
) -> None:
    case = UnsafeQueryCase(
        key="delete_query",
        category="write_operation",
        sql="DELETE FROM products",
        expected_error="non_select_statement",
    )

    report = run_safety_evaluation((case,))
    output_path = tmp_path / "safety_report.json"

    write_safety_evaluation_report(
        report,
        output_path,
    )

    saved_report = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved_report["metrics"] == {
        "total_queries": 1,
        "blocked_queries": 1,
        "blocking_rate_pct": 100.0,
        "expected_reason_matches": 1,
        "failed_cases": 0,
    }
    assert saved_report["outcomes"][0]["passed"] is True
