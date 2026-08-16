from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from langgraph.types import Command

from agentic_bi_copilot.agent.graph import get_agent_graph
from agentic_bi_copilot.schemas import (
    AgentApprovalResponse,
    AgentDecisionRequest,
    AgentResultResponse,
    AgentResumeResponse,
    AgentStartResponse,
    DeclineFindingResponse,
    ManualQueryResponse,
    QueryRequest,
    SQLSafetyResponse,
)
from agentic_bi_copilot.services.manual_pipeline import (
    ManualPipelineResult,
    UnsupportedQuestionError,
    run_manual_pipeline,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["analytics"],
)

# Store agent runs that are waiting for a decision.
ACTIVE_AGENT_RUNS: set[str] = set()


def _create_graph_config(
    thread_id: str,
) -> dict[str, dict[str, str]]:
    """Create the LangGraph configuration for one agent run."""
    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }


def _build_manual_response(
    result: ManualPipelineResult,
) -> ManualQueryResponse:
    """Convert a manual pipeline result into an API response."""
    safety = SQLSafetyResponse(
        is_safe=result.validation.is_safe,
        referenced_tables=list(result.validation.referenced_tables),
        checks=list(result.validation.checks),
        errors=list(result.validation.errors),
    )

    findings = [
        DeclineFindingResponse(
            region=finding.region,
            month=finding.month,
            revenue=finding.revenue,
            previous_month_revenue=(finding.previous_month_revenue),
            change_pct=finding.change_pct,
        )
        for finding in result.analysis.unusual_declines
    ]

    return ManualQueryResponse(
        question=result.question,
        analysis_plan=list(result.analysis_plan),
        selected_tables=list(result.selected_tables),
        sql=result.sql,
        safety=safety,
        columns=result.columns,
        rows=result.rows,
        total_revenue=result.analysis.total_revenue,
        top_region=result.analysis.top_region,
        top_region_revenue=(result.analysis.top_region_revenue),
        findings=findings,
        chart=result.chart,
        answer=result.answer,
        follow_up_questions=list(result.follow_up_questions),
        execution_time_ms=result.execution_time_ms,
    )


def _get_approval_request(
    state: dict[str, Any],
) -> AgentApprovalResponse | None:
    """Get and validate an approval request from graph state."""
    interrupts = state.get("__interrupt__", ())

    if not interrupts:
        return None

    approval_value = interrupts[0].value

    if not isinstance(approval_value, dict):
        raise HTTPException(
            status_code=(status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=("The approval request was not a valid object."),
        )

    return AgentApprovalResponse.model_validate(approval_value)


@router.post(
    "/manual-query",
    response_model=ManualQueryResponse,
)
def manual_query(
    request: QueryRequest,
) -> ManualQueryResponse:
    """Run the deterministic analytics pipeline."""
    try:
        result = run_manual_pipeline(request.question)
    except UnsupportedQuestionError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return _build_manual_response(result)


@router.post(
    "/agent/runs",
    response_model=AgentStartResponse,
)
def start_agent_run(
    request: QueryRequest,
) -> AgentStartResponse:
    """Start an agent run and pause for SQL approval."""
    thread_id = str(uuid4())
    config = _create_graph_config(thread_id)
    graph = get_agent_graph()

    state = graph.invoke(
        {
            "question": request.question,
        },
        config=config,
    )

    approval = _get_approval_request(state)

    if approval is None:
        return AgentStartResponse(
            thread_id=thread_id,
            status="failed",
            error=(
                state.get("error") or ("The workflow ended before requesting approval.")
            ),
        )

    ACTIVE_AGENT_RUNS.add(thread_id)

    return AgentStartResponse(
        thread_id=thread_id,
        status="awaiting_approval",
        approval=approval,
    )


@router.post(
    "/agent/runs/{thread_id}/decision",
    response_model=AgentResumeResponse,
)
def decide_agent_run(
    thread_id: str,
    request: AgentDecisionRequest,
) -> AgentResumeResponse:
    """Approve or reject a paused agent run."""
    if thread_id not in ACTIVE_AGENT_RUNS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=("Agent run was not found or is no longer active."),
        )

    graph = get_agent_graph()
    config = _create_graph_config(thread_id)

    try:
        state = graph.invoke(
            Command(
                resume={
                    "approved": request.approved,
                    "feedback": request.feedback,
                }
            ),
            config=config,
        )
    finally:
        # A run can only be approved or rejected once.
        ACTIVE_AGENT_RUNS.discard(thread_id)

    if not request.approved:
        return AgentResumeResponse(
            thread_id=thread_id,
            status="rejected",
            approved=False,
            error=(state.get("rejection_reason") or state.get("error")),
        )

    if state.get("error"):
        return AgentResumeResponse(
            thread_id=thread_id,
            status="failed",
            approved=True,
            error=state["error"],
        )

    return AgentResumeResponse(
        thread_id=thread_id,
        status="completed",
        approved=True,
        result=build_agent_result(state),
    )


def build_agent_result(
    state: dict[str, Any],
) -> AgentResultResponse:
    """Convert completed graph state into an API result."""
    return AgentResultResponse(
        question=state["question"],
        plan=state["plan"],
        sql=state["sql"],
        sql_explanation=state["sql_explanation"],
        referenced_tables=state["referenced_tables"],
        validation=state["validation"],
        query_result=state["query_result"],
        analysis=state["analysis"],
        answer=state["answer"],
        follow_up_questions=list(state.get("follow_up_questions", [])),
        chart=state["chart"],
    )
