from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from langgraph.types import interrupt

from agentic_bi_copilot.agent.state import AgentState
from agentic_bi_copilot.database.query_service import (
    execute_validated_query,
)
from agentic_bi_copilot.database.schema_service import build_schema_context
from agentic_bi_copilot.schemas import AnalysisPlan
from agentic_bi_copilot.security.sql_validator import validate_sql
from agentic_bi_copilot.services.analysis import analyze_regional_revenue
from agentic_bi_copilot.services.charts import (
    chart_to_spec,
    create_regional_revenue_chart,
)
from agentic_bi_copilot.services.llm import create_analysis_plan, generate_sql
from agentic_bi_copilot.services.manual_pipeline import create_business_answer

DECLINE_THRESHOLD = Decimal(-25)
AGENT_TABLES = (
    "regions",
    "customers",
    "orders",
    "order_items",
    "products",
    "monthly_targets",
)


def schema_discovery_node(state: AgentState) -> AgentState:
    del state

    return {
        "schema_context": build_schema_context(AGENT_TABLES),
        "error": None,
    }


def planning_node(state: AgentState) -> AgentState:
    plan = create_analysis_plan(
        question=state["question"],
        schema_context=state["schema_context"],
    )

    return {
        "plan": plan.model_dump(mode="json"),
        "error": None,
    }


def sql_generation_node(state: AgentState) -> AgentState:
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
    validation = validate_sql(state["sql"])

    error = None

    if not validation.is_safe:
        error = "SQL validation failed: " + ", ".join(validation.errors)

    return {
        "validation": {
            "is_safe": validation.is_safe,
            "normalized_sql": validation.normalized_sql,
            "referenced_tables": list(validation.referenced_tables),
            "checks": list(validation.checks),
            "errors": list(validation.errors),
        },
        "error": error,
    }


def human_approval_node(state: AgentState) -> AgentState:
    decision = interrupt(
        {
            "type": "sql_approval",
            "question": state["question"],
            "sql": state["sql"],
            "sql_explanation": state["sql_explanation"],
            "referenced_tables": state["referenced_tables"],
            "validation": state["validation"],
        }
    )

    if not isinstance(decision, dict):
        raise TypeError("Approval response must be an object.")

    approved = decision.get("approved")
    feedback = decision.get("feedback")

    if not isinstance(approved, bool):
        raise TypeError("Approval response must include an approved boolean.")

    if feedback is not None and not isinstance(feedback, str):
        raise TypeError("Approval feedback must be text or null.")

    if approved:
        return {
            "approved": True,
            "rejection_reason": None,
            "error": None,
        }

    return {
        "approved": False,
        "rejection_reason": feedback or "SQL execution was rejected.",
        "error": "SQL execution was rejected by the reviewer.",
    }

def query_execution_node(state: AgentState) -> AgentState:
    if state.get("approved") is not True:
        raise PermissionError(
            "SQL execution requires explicit human approval."
        )

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
            "execution_time_ms": query_result.execution_time_ms,
        },
        "error": None,
    }


def analysis_node(state: AgentState) -> AgentState:
    query_result = state.get("query_result")

    if not isinstance(query_result, dict):
        raise TypeError("Query result must be an object.")

    rows = query_result.get("rows")

    if not isinstance(rows, list):
        raise TypeError("Query result rows must be a list.")

    analysis = analyze_regional_revenue(
        rows,
        decline_threshold=DECLINE_THRESHOLD,
    )
    serialized_analysis = jsonable_encoder(analysis)

    if not isinstance(serialized_analysis, dict):
        raise TypeError("Serialized analysis must be an object.")

    return {
        "analysis": serialized_analysis,
        "answer": create_business_answer(analysis),
        "error": None,
    }


def chart_node(state: AgentState) -> AgentState:
    query_result = state.get("query_result")

    if not isinstance(query_result, dict):
        raise TypeError("Query result must be an object.")

    rows = query_result.get("rows")

    if not isinstance(rows, list):
        raise TypeError("Query result rows must be a list.")

    analysis = analyze_regional_revenue(
        rows,
        decline_threshold=DECLINE_THRESHOLD,
    )
    figure = create_regional_revenue_chart(rows, analysis)
    chart = jsonable_encoder(chart_to_spec(figure))

    if not isinstance(chart, dict):
        raise TypeError("Serialized chart must be an object.")

    return {
        "chart": chart,
        "error": None,
    }