from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from agentic_bi_copilot.api.main import app
from agentic_bi_copilot.schemas import AgentStartResponse

client = TestClient(app)


def create_completed_result(
    question: str,
) -> dict[str, Any]:
    """Create a valid stored agent result."""

    return {
        "question": question,
        "plan": {},
        "sql": "SELECT name FROM regions LIMIT 10",
        "sql_explanation": "Lists available regions.",
        "referenced_tables": ["regions"],
        "validation": {
            "is_safe": True,
        },
        "query_result": {
            "columns": ["name"],
            "rows": [{"name": "North"}],
            "row_count": 1,
            "execution_time_ms": 1.0,
        },
        "analysis": {
            "analysis_type": "ranking",
        },
        "answer": "North is an available region.",
        "follow_up_questions": [],
        "chart": {
            "data": [],
            "layout": {},
        },
    }


def create_history_record(
    *,
    thread_id: str = "run-123",
    status: str = "completed",
    result: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """Create a small history-record replacement."""

    timestamp = datetime.now(UTC)

    return SimpleNamespace(
        thread_id=thread_id,
        question="Which regions are available?",
        status=status,
        source_thread_id=None,
        result=result,
        error=None,
        created_at=timestamp,
        updated_at=timestamp,
        approval=None,
    )


def test_lists_agent_run_history() -> None:
    question = "Which regions are available?"

    record = create_history_record(
        result=create_completed_result(question),
    )

    with patch(
        "agentic_bi_copilot.api.routes.list_runs",
        return_value=[record],
    ):
        response = client.get("/api/v1/agent/runs/history?limit=10")

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["runs"][0]["thread_id"] == "run-123"
    assert body["runs"][0]["status"] == "completed"
    assert body["runs"][0]["has_result"] is True


def test_returns_agent_run_detail() -> None:
    question = "Which regions are available?"

    record = create_history_record(
        result=create_completed_result(question),
    )

    with patch(
        "agentic_bi_copilot.api.routes.get_run",
        return_value=record,
    ):
        response = client.get("/api/v1/agent/runs/run-123")

    assert response.status_code == 200

    body = response.json()

    assert body["thread_id"] == "run-123"
    assert body["status"] == "completed"
    assert body["result"]["answer"] == ("North is an available region.")


def test_unknown_run_detail_returns_not_found() -> None:
    with patch(
        "agentic_bi_copilot.api.routes.get_run",
        return_value=None,
    ):
        response = client.get("/api/v1/agent/runs/unknown-run")

    assert response.status_code == 404
    assert response.json()["detail"] == ("Agent run was not found.")


def test_retries_finished_agent_run() -> None:
    record = create_history_record(
        status="completed",
    )

    start_response = AgentStartResponse(
        thread_id="retry-run",
        status="failed",
        error="Test retry response.",
    )

    with (
        patch(
            "agentic_bi_copilot.api.routes.get_run",
            return_value=record,
        ),
        patch(
            "agentic_bi_copilot.api.routes._start_agent_workflow",
            return_value=start_response,
        ) as start_mock,
    ):
        response = client.post("/api/v1/agent/runs/run-123/retry")

    assert response.status_code == 200

    body = response.json()

    assert body["thread_id"] == "retry-run"
    assert body["source_thread_id"] == "run-123"

    start_mock.assert_called_once_with(
        question=record.question,
        source_thread_id="run-123",
    )


def test_does_not_retry_run_awaiting_approval() -> None:
    record = create_history_record(
        status="awaiting_approval",
    )

    with patch(
        "agentic_bi_copilot.api.routes.get_run",
        return_value=record,
    ):
        response = client.post("/api/v1/agent/runs/run-123/retry")

    assert response.status_code == 409
    assert "still awaiting approval" in (response.json()["detail"])


def test_downloads_completed_run_as_json() -> None:
    question = "Which regions are available?"

    record = create_history_record(
        status="completed",
        result=create_completed_result(question),
    )

    with patch(
        "agentic_bi_copilot.api.routes.get_run",
        return_value=record,
    ):
        response = client.get("/api/v1/agent/runs/run-123/export?format=json")

    assert response.status_code == 200
    assert response.headers["content-type"] == ("application/json")
    assert response.headers["content-disposition"] == (
        'attachment; filename="analysis-run-123.json"'
    )

    body = response.json()

    assert body["thread_id"] == "run-123"
    assert body["result"]["answer"] == ("North is an available region.")


def test_downloads_completed_run_as_csv() -> None:
    question = "Which regions are available?"

    record = create_history_record(
        status="completed",
        result=create_completed_result(question),
    )

    with patch(
        "agentic_bi_copilot.api.routes.get_run",
        return_value=record,
    ):
        response = client.get("/api/v1/agent/runs/run-123/export?format=csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="analysis-run-123.csv"'
    )
    assert response.text.splitlines() == [
        "name",
        "North",
    ]


def test_does_not_export_unfinished_run() -> None:
    record = create_history_record(
        status="failed",
        result=None,
    )

    with patch(
        "agentic_bi_copilot.api.routes.get_run",
        return_value=record,
    ):
        response = client.get("/api/v1/agent/runs/run-123/export?format=json")

    assert response.status_code == 409
    assert response.json()["detail"] == ("Only completed agent runs can be exported.")


def test_rejects_unknown_export_format() -> None:
    response = client.get("/api/v1/agent/runs/run-123/export?format=pdf")

    assert response.status_code == 422
