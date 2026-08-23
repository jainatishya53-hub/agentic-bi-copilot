from datetime import UTC, datetime

from agentic_bi_copilot.schemas import (
    AgentRetryResponse,
    AgentRunDetailResponse,
    AgentRunHistoryResponse,
    AgentRunSummaryResponse,
)


def create_run_summary() -> AgentRunSummaryResponse:
    """Create a reusable run-history summary for tests."""

    timestamp = datetime.now(UTC)

    return AgentRunSummaryResponse(
        thread_id="run-123",
        question="Which region generated the highest revenue?",
        status="completed",
        source_thread_id=None,
        has_result=True,
        error=None,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_creates_run_history_response() -> None:
    summary = create_run_summary()

    history = AgentRunHistoryResponse(
        runs=[summary],
        total=1,
    )

    assert history.total == 1
    assert history.runs[0].thread_id == "run-123"
    assert history.runs[0].status == "completed"
    assert history.runs[0].has_result is True


def test_creates_run_detail_with_result() -> None:
    summary = create_run_summary()

    detail = AgentRunDetailResponse(
        **summary.model_dump(),
        result={
            "question": summary.question,
            "plan": {},
            "sql": "SELECT name FROM regions LIMIT 10",
            "sql_explanation": "Lists available regions.",
            "referenced_tables": ["regions"],
            "validation": {"is_safe": True},
            "query_result": {
                "columns": ["name"],
                "rows": [{"name": "North"}],
                "row_count": 1,
                "execution_time_ms": 1.0,
            },
            "analysis": {"analysis_type": "ranking"},
            "answer": "North is an available region.",
            "follow_up_questions": [],
            "chart": {"data": [], "layout": {}},
        },
    )

    assert detail.result is not None
    assert detail.result.answer == "North is an available region."
    assert detail.result.query_result["row_count"] == 1


def test_creates_retry_response() -> None:
    response = AgentRetryResponse(
        thread_id="new-run",
        source_thread_id="original-run",
        status="failed",
        error="The retry could not be started.",
    )

    assert response.thread_id == "new-run"
    assert response.source_thread_id == "original-run"
    assert response.status == "failed"
