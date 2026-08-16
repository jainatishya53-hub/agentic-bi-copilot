from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder
from langgraph.types import interrupt

from agentic_bi_copilot.agent.state import AgentState
from agentic_bi_copilot.database.query_service import (
    execute_validated_query,
)
from agentic_bi_copilot.database.schema_service import (
    build_schema_context,
)
from agentic_bi_copilot.schemas import AnalysisPlan
from agentic_bi_copilot.security.sql_validator import (
    SQLValidationResult,
    validate_sql,
)
from agentic_bi_copilot.services.analysis import (
    RevenueAnalysis,
    analyze_regional_revenue,
)
from agentic_bi_copilot.services.charts import (
    chart_to_spec,
    create_regional_revenue_chart,
)
from agentic_bi_copilot.services.llm import (
    create_analysis_plan,
    generate_sql,
)
from agentic_bi_copilot.services.manual_pipeline import (
    create_business_answer,
)

DECLINE_THRESHOLD = Decimal(-25)

AGENT_TABLES = (
    "regions",
    "customers",
    "orders",
    "order_items",
    "products",
    "monthly_targets",
)

FOLLOW_UP_QUESTIONS = (
    "Which products contributed most to the unusual declines?",
    "How did each region perform against its monthly revenue targets?",
    "Which customer segments drove the regional revenue changes?",
)


def _serialize_validation(
    validation: SQLValidationResult,
) -> dict[str, Any]:
    """Convert a validation result into graph state data."""
    return {
        "is_safe": validation.is_safe,
        "normalized_sql": validation.normalized_sql,
        "referenced_tables": list(validation.referenced_tables),
        "checks": list(validation.checks),
        "errors": list(validation.errors),
    }


def _validate_approval_response(
    decision: object,
) -> tuple[bool, str | None]:
    """Validate the response received from the reviewer."""
    if not isinstance(decision, dict):
        raise TypeError("Approval response must be an object.")

    approved = decision.get("approved")
    feedback = decision.get("feedback")

    if not isinstance(approved, bool):
        raise TypeError("Approval response must include an approved boolean.")

    if feedback is not None and not isinstance(feedback, str):
        raise TypeError("Approval feedback must be text or null.")

    return approved, feedback


def _get_query_rows(
    state: AgentState,
) -> list[dict[str, Any]]:
    """Get and validate query rows stored in graph state."""
    query_result = state.get("query_result")

    if not isinstance(query_result, dict):
        raise TypeError("Query result must be an object.")

    rows = query_result.get("rows")

    if not isinstance(rows, list):
        raise TypeError("Query result rows must be a list.")

    return rows


def _analyze_rows(
    rows: list[dict[str, Any]],
) -> RevenueAnalysis:
    """Analyze query rows using the agent decline threshold."""
    return analyze_regional_revenue(
        rows,
        decline_threshold=DECLINE_THRESHOLD,
    )


def schema_discovery_node(state: AgentState) -> AgentState:
    """Load the database schema context for the agent."""
    del state

    return {
        "schema_context": build_schema_context(AGENT_TABLES),
        "error": None,
    }


def planning_node(state: AgentState) -> AgentState:
    """Create the structured business analysis plan."""
    plan = create_analysis_plan(
        question=state["question"],
        schema_context=state["schema_context"],
    )

    return {
        "plan": plan.model_dump(mode="json"),
        "error": None,
    }


def sql_generation_node(state: AgentState) -> AgentState:
    """Generate a SQL draft from the approved plan."""
    plan = AnalysisPlan.model_validate(state["plan"])

    draft = generate_sql(
        question=state["question"],
        plan=plan,
        schema_context=state["schema_context"],
    )

    return {
        "sql": draft.sql,
        "sql_explanation": draft.explanation,
        "referenced_tables": draft.referenced_tables,
        "error": None,
    }


def sql_validation_node(state: AgentState) -> AgentState:
    """Run all SQL safety checks."""
    validation = validate_sql(state["sql"])
    error = None

    if not validation.is_safe:
        error = "SQL validation failed: " + ", ".join(validation.errors)

    return {
        "validation": _serialize_validation(validation),
        "error": error,
    }


def human_approval_node(state: AgentState) -> AgentState:
    """Pause the workflow until a reviewer accepts or rejects SQL."""
    decision = interrupt(
        {
            "type": "sql_approval",
            "question": state["question"],
            "plan": state["plan"],
            "sql": state["sql"],
            "sql_explanation": state["sql_explanation"],
            "referenced_tables": state["referenced_tables"],
            "validation": state["validation"],
        }
    )

    approved, feedback = _validate_approval_response(decision)

    if approved:
        return {
            "approved": True,
            "rejection_reason": None,
            "error": None,
        }

    return {
        "approved": False,
        "rejection_reason": (feedback or "SQL execution was rejected."),
        "error": ("SQL execution was rejected by the reviewer."),
    }


def query_execution_node(state: AgentState) -> AgentState:
    """Execute SQL only after explicit human approval."""
    if state.get("approved") is not True:
        raise PermissionError("SQL execution requires explicit human approval.")

    validated_result = execute_validated_query(state["sql"])
    query_result = validated_result.query_result
    serialized_rows = jsonable_encoder(query_result.rows)

    if not isinstance(serialized_rows, list):
        raise TypeError("Serialized query rows must be a list.")

    return {
        "query_result": {
            "columns": list(query_result.columns),
            "rows": serialized_rows,
            "row_count": query_result.row_count,
            "execution_time_ms": (query_result.execution_time_ms),
        },
        "error": None,
    }


def analysis_node(state: AgentState) -> AgentState:
    """Analyze query rows and create the business answer."""
    rows = _get_query_rows(state)
    analysis = _analyze_rows(rows)
    serialized_analysis = jsonable_encoder(analysis)

    if not isinstance(serialized_analysis, dict):
        raise TypeError("Serialized analysis must be an object.")

    return {
        "analysis": serialized_analysis,
        "answer": create_business_answer(analysis),
        "follow_up_questions": list(FOLLOW_UP_QUESTIONS),
        "error": None,
    }


def chart_node(state: AgentState) -> AgentState:
    """Create the chart from the approved query result."""
    rows = _get_query_rows(state)
    analysis = _analyze_rows(rows)

    figure = create_regional_revenue_chart(
        rows,
        analysis,
    )
    chart_specification = chart_to_spec(figure)
    serialized_chart = jsonable_encoder(chart_specification)

    if not isinstance(serialized_chart, dict):
        raise TypeError("Serialized chart must be an object.")

    return {
        "chart": serialized_chart,
        "error": None,
    }
