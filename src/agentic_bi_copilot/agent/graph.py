from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agentic_bi_copilot.agent import nodes
from agentic_bi_copilot.agent.state import AgentState


def route_after_validation(state: AgentState) -> str:
    """Continue to approval only when the SQL is safe."""
    validation = state.get("validation")

    if isinstance(validation, dict) and validation.get("is_safe") is True:
        return "human_approval"

    return END


def route_after_approval(state: AgentState) -> str:
    """Execute the query only after explicit approval."""
    if state.get("approved") is True:
        return "execute_query"

    return END


def build_agent_graph():
    """Build and compile the complete agent workflow."""
    workflow = StateGraph(AgentState)

    # Add each processing step to the graph.
    workflow.add_node(
        "discover_schema",
        nodes.schema_discovery_node,
    )
    workflow.add_node(
        "create_plan",
        nodes.planning_node,
    )
    workflow.add_node(
        "generate_sql",
        nodes.sql_generation_node,
    )
    workflow.add_node(
        "validate_sql",
        nodes.sql_validation_node,
    )
    workflow.add_node(
        "human_approval",
        nodes.human_approval_node,
    )
    workflow.add_node(
        "execute_query",
        nodes.query_execution_node,
    )
    workflow.add_node(
        "analyze_results",
        nodes.analysis_node,
    )
    workflow.add_node(
        "create_chart",
        nodes.chart_node,
    )

    # Define the normal processing order.
    workflow.add_edge(START, "discover_schema")
    workflow.add_edge("discover_schema", "create_plan")
    workflow.add_edge("create_plan", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")

    # Unsafe SQL ends the workflow before approval.
    workflow.add_conditional_edges(
        "validate_sql",
        route_after_validation,
        {
            "human_approval": "human_approval",
            END: END,
        },
    )

    # Rejected SQL ends the workflow before execution.
    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "execute_query": "execute_query",
            END: END,
        },
    )

    workflow.add_edge(
        "execute_query",
        "analyze_results",
    )
    workflow.add_edge(
        "analyze_results",
        "create_chart",
    )
    workflow.add_edge("create_chart", END)

    # The checkpointer allows an interrupted workflow to resume.
    checkpointer = InMemorySaver()

    return workflow.compile(checkpointer=checkpointer)


@lru_cache
def get_agent_graph():
    """Create and reuse one resumable agent graph."""
    return build_agent_graph()
