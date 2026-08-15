from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from agentic_bi_copilot.api.main import app
from agentic_bi_copilot.api.routes import ACTIVE_AGENT_RUNS

client = TestClient(app)


def setup_function() -> None:
    ACTIVE_AGENT_RUNS.clear()


def test_start_agent_run_returns_approval_request() -> None:
    approval = {
        "type": "sql_approval",
        "question": "Compare regional revenue.",
        "sql": "SELECT name FROM regions LIMIT 10",
        "sql_explanation": "Lists regions.",
        "referenced_tables": ["regions"],
        "validation": {
            "is_safe": True,
            "errors": [],
        },
    }

    fake_graph = Mock()
    fake_graph.invoke.return_value = {
        "__interrupt__": (
            SimpleNamespace(value=approval),
        )
    }

    with (
        patch(
            "agentic_bi_copilot.api.routes.get_agent_graph",
            return_value=fake_graph,
        ),
        patch(
            "agentic_bi_copilot.api.routes.uuid4",
            return_value="test-thread",
        ),
    ):
        response = client.post(
            "/api/v1/agent/runs",
            json={
                "question": "Compare regional revenue.",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == "test-thread"
    assert body["status"] == "awaiting_approval"
    assert body["approval"]["sql"] == approval["sql"]
    assert "test-thread" in ACTIVE_AGENT_RUNS


def test_approve_agent_run_returns_completed_result() -> None:
    thread_id = "approved-thread"
    ACTIVE_AGENT_RUNS.add(thread_id)

    fake_graph = Mock()
    fake_graph.invoke.return_value = {
        "question": "Compare regional revenue.",
        "plan": {
            "steps": ["Calculate regional revenue."],
        },
        "sql": "SELECT name FROM regions LIMIT 10",
        "sql_explanation": "Lists regions.",
        "referenced_tables": ["regions"],
        "validation": {
            "is_safe": True,
            "errors": [],
        },
        "approved": True,
        "query_result": {
            "columns": ["name"],
            "rows": [{"name": "North"}],
            "row_count": 1,
            "execution_time_ms": 1.0,
        },
        "analysis": {
            "top_region": "North",
        },
        "answer": "North generated the highest revenue.",
        "chart": {
            "data": [{"type": "scatter"}],
            "layout": {},
        },
        "error": None,
    }

    with patch(
        "agentic_bi_copilot.api.routes.get_agent_graph",
        return_value=fake_graph,
    ):
        response = client.post(
            f"/api/v1/agent/runs/{thread_id}/decision",
            json={
                "approved": True,
                "feedback": None,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["approved"] is True
    assert body["result"]["answer"] == (
        "North generated the highest revenue."
    )
    assert body["result"]["query_result"]["row_count"] == 1
    assert thread_id not in ACTIVE_AGENT_RUNS


def test_reject_agent_run_returns_rejection() -> None:
    thread_id = "rejected-thread"
    ACTIVE_AGENT_RUNS.add(thread_id)

    fake_graph = Mock()
    fake_graph.invoke.return_value = {
        "approved": False,
        "rejection_reason": "The SQL needs another filter.",
        "error": "SQL execution was rejected by the reviewer.",
    }

    with patch(
        "agentic_bi_copilot.api.routes.get_agent_graph",
        return_value=fake_graph,
    ):
        response = client.post(
            f"/api/v1/agent/runs/{thread_id}/decision",
            json={
                "approved": False,
                "feedback": "The SQL needs another filter.",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["approved"] is False
    assert body["result"] is None
    assert body["error"] == "The SQL needs another filter."
    assert thread_id not in ACTIVE_AGENT_RUNS


def test_unknown_agent_run_returns_not_found() -> None:
    response = client.post(
        "/api/v1/agent/runs/unknown-thread/decision",
        json={
            "approved": True,
            "feedback": None,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Agent run was not found or is no longer active."
    )