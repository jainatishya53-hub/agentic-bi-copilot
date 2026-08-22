from uuid import uuid4

import pytest
from langgraph.types import Command

from agentic_bi_copilot.agent import nodes
from agentic_bi_copilot.agent.graph import build_agent_graph
from agentic_bi_copilot.agent.persistence import (
    close_checkpoint_pool,
    get_postgres_checkpointer,
    setup_checkpoint_database,
)
from agentic_bi_copilot.agent.state import AgentState


def fake_schema_discovery_node(_state: AgentState) -> AgentState:
    """Return a small schema result without accessing the database."""

    return {
        "schema_context": "Table: regions",
        "selected_tables": ["regions"],
    }


def fake_planning_node(state: AgentState) -> AgentState:
    """Return a simple analysis plan without calling the language model."""

    return {
        "plan": {
            "interpreted_question": state["question"],
            "required_tables": ["regions"],
            "steps": ["Read the available regions."],
            "assumptions": [],
            "needs_clarification": False,
            "clarification_question": None,
        }
    }


def fake_sql_generation_node(_state: AgentState) -> AgentState:
    """Return safe SQL without calling the language model."""

    return {
        "sql": "SELECT name FROM regions ORDER BY name LIMIT 10",
        "sql_explanation": "Lists the available regions.",
        "referenced_tables": ["regions"],
    }


def fake_sql_validation_node(state: AgentState) -> AgentState:
    """Return a successful SQL validation result."""

    return {
        "validation": {
            "is_safe": True,
            "normalized_sql": state["sql"],
            "referenced_tables": ["regions"],
            "checks": ["select_only", "valid_row_limit"],
            "errors": [],
        }
    }


def fake_query_execution_node(state: AgentState) -> AgentState:
    """Return a small query result after approval."""

    assert state["approved"] is True

    return {
        "query_result": {
            "columns": ["name"],
            "rows": [{"name": "North"}],
            "row_count": 1,
            "execution_time_ms": 1.0,
        }
    }


def fake_analysis_node(_state: AgentState) -> AgentState:
    """Return a simple business answer."""

    return {
        "analysis": {
            "analysis_type": "ranking",
            "summary": "North is an available region.",
            "key_findings": ["North was returned by the query."],
        },
        "answer": "North is an available region.",
        "follow_up_questions": [],
    }


def fake_chart_node(_state: AgentState) -> AgentState:
    """Return a small chart specification."""

    return {
        "chart": {
            "data": [{"type": "bar"}],
            "layout": {},
        }
    }


def replace_external_workflow_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replace external services with predictable test functions."""

    monkeypatch.setattr(
        nodes,
        "schema_discovery_node",
        fake_schema_discovery_node,
    )
    monkeypatch.setattr(
        nodes,
        "planning_node",
        fake_planning_node,
    )
    monkeypatch.setattr(
        nodes,
        "sql_generation_node",
        fake_sql_generation_node,
    )
    monkeypatch.setattr(
        nodes,
        "sql_validation_node",
        fake_sql_validation_node,
    )
    monkeypatch.setattr(
        nodes,
        "query_execution_node",
        fake_query_execution_node,
    )
    monkeypatch.setattr(
        nodes,
        "analysis_node",
        fake_analysis_node,
    )
    monkeypatch.setattr(
        nodes,
        "chart_node",
        fake_chart_node,
    )


def test_paused_workflow_resumes_after_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirm that PostgreSQL preserves a paused workflow."""

    replace_external_workflow_steps(monkeypatch)
    setup_checkpoint_database()

    thread_id = f"persistence-test-{uuid4()}"
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    try:
        first_checkpointer = get_postgres_checkpointer()
        first_graph = build_agent_graph(
            checkpointer=first_checkpointer,
        )

        paused = first_graph.invoke(
            {"question": "Which regions are available?"},
            config=config,
        )

        assert paused["__interrupt__"]

        # Closing the pool simulates the API process stopping.
        close_checkpoint_pool()

        # A new pool and graph simulate a fresh API process.
        second_checkpointer = get_postgres_checkpointer()
        second_graph = build_agent_graph(
            checkpointer=second_checkpointer,
        )

        completed = second_graph.invoke(
            Command(
                resume={
                    "approved": True,
                    "feedback": None,
                }
            ),
            config=config,
        )

        assert completed["approved"] is True
        assert completed["query_result"]["row_count"] == 1
        assert completed["query_result"]["rows"] == [{"name": "North"}]
        assert completed["answer"] == "North is an available region."
    finally:
        # Remove this test thread so test data does not accumulate.
        checkpointer = get_postgres_checkpointer()
        checkpointer.delete_thread(thread_id)
        close_checkpoint_pool()
