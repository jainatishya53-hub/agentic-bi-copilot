from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from agentic_bi_copilot.api.main import app

client = TestClient(app)


def test_start_agent_run_returns_approval_request() -> None:
    question = "Compare regional revenue."

    approval = {
        "type": "sql_approval",
        "question": question,
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
        "__interrupt__": (SimpleNamespace(value=approval),)
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
        patch(
            "agentic_bi_copilot.api.routes.create_run",
        ) as create_run_mock,
        patch(
            "agentic_bi_copilot.api.routes.update_run",
        ) as update_run_mock,
    ):
        response = client.post(
            "/api/v1/agent/runs",
            json={
                "question": question,
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["thread_id"] == "test-thread"
    assert body["status"] == "awaiting_approval"
    assert body["approval"]["sql"] == approval["sql"]

    create_run_mock.assert_called_once_with(
        thread_id="test-thread",
        question=question,
        status="awaiting_approval",
        source_thread_id=None,
    )

    update_run_mock.assert_called_once_with(
        thread_id="test-thread",
        status="awaiting_approval",
        approval=body["approval"],
    )


def test_approve_agent_run_returns_completed_result() -> None:
    thread_id = "approved-thread"
    active_run = SimpleNamespace(
        status="awaiting_approval",
    )

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

    with (
        patch(
            "agentic_bi_copilot.api.routes.get_run",
            return_value=active_run,
        ),
        patch(
            "agentic_bi_copilot.api.routes.get_agent_graph",
            return_value=fake_graph,
        ),
        patch(
            "agentic_bi_copilot.api.routes.update_run",
        ) as update_run_mock,
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
    assert body["result"]["answer"] == ("North generated the highest revenue.")
    assert body["result"]["query_result"]["row_count"] == 1

    update_call = update_run_mock.call_args.kwargs

    assert update_call["thread_id"] == thread_id
    assert update_call["status"] == "completed"
    assert update_call["result"]["answer"] == ("North generated the highest revenue.")


def test_reject_agent_run_returns_rejection() -> None:
    thread_id = "rejected-thread"
    active_run = SimpleNamespace(
        status="awaiting_approval",
    )

    fake_graph = Mock()
    fake_graph.invoke.return_value = {
        "approved": False,
        "rejection_reason": "The SQL needs another filter.",
        "error": "SQL execution was rejected by the reviewer.",
    }

    with (
        patch(
            "agentic_bi_copilot.api.routes.get_run",
            return_value=active_run,
        ),
        patch(
            "agentic_bi_copilot.api.routes.get_agent_graph",
            return_value=fake_graph,
        ),
        patch(
            "agentic_bi_copilot.api.routes.update_run",
        ) as update_run_mock,
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

    update_run_mock.assert_called_once_with(
        thread_id=thread_id,
        status="rejected",
        error="The SQL needs another filter.",
    )


def test_unknown_agent_run_returns_not_found() -> None:
    with patch(
        "agentic_bi_copilot.api.routes.get_run",
        return_value=None,
    ):
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
