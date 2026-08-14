from datetime import date

import pytest

from agentic_bi_copilot.services.manual_pipeline import (
    PRIMARY_QUESTION,
    UnsupportedQuestionError,
    run_manual_pipeline,
)


def test_runs_complete_manual_pipeline() -> None:
    result = run_manual_pipeline(PRIMARY_QUESTION)

    assert result.validation.is_safe
    assert result.validation.errors == ()
    assert result.selected_tables == (
        "customers",
        "order_items",
        "orders",
        "regions",
    )
    assert len(result.rows) == 24
    assert result.analysis.top_region == "North"
    assert result.analysis.unusual_declines[0].region == "West"
    assert result.analysis.unusual_declines[0].month == date(
        2026,
        7,
        1,
    )
    assert len(result.chart["data"]) == 5
    assert "North generated the highest revenue" in result.answer
    assert len(result.follow_up_questions) == 3


def test_rejects_unsupported_manual_question() -> None:
    with pytest.raises(
        UnsupportedQuestionError,
        match="currently supports only",
    ):
        run_manual_pipeline("Which products sold the most?")