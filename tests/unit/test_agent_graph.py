from unittest.mock import patch
from uuid import uuid4

from langgraph.types import Command

from agentic_bi_copilot.agent import nodes
from agentic_bi_copilot.agent.graph import build_agent_graph
from agentic_bi_copilot.agent.state import AgentState


def build_test_graph(*, sql_is_safe: bool):
    def schema_node(state: AgentState) -> AgentState:
        del state
        return {"schema_context": "test schema", "error": None}

    def plan_node(state: AgentState) -> AgentState:
        del state
        return {
            "plan": {
                "interpreted_question": "List regions.",
                "required_tables": ["regions"],
                "steps": ["List regions."],
                "assumptions": [],
                "needs_clarification": False,
                "clarification_question": None,
            },
            "error": None,
        }

    def generation_node(state: AgentState) -> AgentState:
        del state
        return {
            "sql": "SELECT name FROM regions ORDER BY name LIMIT 10",
            "sql_explanation": "Lists regions.",
            "referenced_tables": ["regions"],
            "error": None,
        }

    def validation_node(state: AgentState) -> AgentState:
        return {
            "validation": {
                "is_safe": sql_is_safe,
                "normalized_sql": state["sql"] if sql_is_safe else None,
                "referenced_tables": ["regions"],
                "checks": ["single_statement"] if sql_is_safe else [],
                "errors": [] if sql_is_safe else ["unsafe query"],
            },
            "error": None if sql_is_safe else "SQL validation failed.",
        }

    with (
            patch.object(nodes, "schema_discovery_node", schema_node),
            patch.object(nodes, "planning_node", plan_node),
            patch.object(nodes, "sql_generation_node", generation_node),
            patch.object(nodes, "sql_validation_node", validation_node),
        ):
            return build_agent_graph()


def test_safe_sql_pauses_and_resumes_with_approval() -> None:
    graph = build_test_graph(sql_is_safe=True)
    config = {"configurable": {"thread_id": str(uuid4())}}

    paused = graph.invoke({"question": "List regions."}, config=config)

    assert "__interrupt__" in paused
    interrupt_payload = paused["__interrupt__"][0].value
    assert interrupt_payload["type"] == "sql_approval"
    assert interrupt_payload["referenced_tables"] == ["regions"]

    completed = graph.invoke(
        Command(
            resume={
                "approved": True,
                "feedback": None,
            }
        ),
        config=config,
    )

    assert completed["approved"] is True
    assert completed["rejection_reason"] is None
    assert completed["error"] is None


def test_safe_sql_can_be_rejected() -> None:
    graph = build_test_graph(sql_is_safe=True)
    config = {"configurable": {"thread_id": str(uuid4())}}

    paused = graph.invoke({"question": "List regions."}, config=config)
    assert "__interrupt__" in paused

    completed = graph.invoke(
        Command(
            resume={
                "approved": False,
                "feedback": "The query needs another filter.",
            }
        ),
        config=config,
    )

    assert completed["approved"] is False
    assert completed["rejection_reason"] == "The query needs another filter."
    assert completed["error"] == "SQL execution was rejected by the reviewer."


def test_unsafe_sql_never_reaches_approval() -> None:
    graph = build_test_graph(sql_is_safe=False)
    config = {"configurable": {"thread_id": str(uuid4())}}

    completed = graph.invoke({"question": "List regions."}, config=config)

    assert "__interrupt__" not in completed
    assert completed["validation"]["is_safe"] is False
    assert completed.get("approved") is not True
    assert completed["error"] == "SQL validation failed."