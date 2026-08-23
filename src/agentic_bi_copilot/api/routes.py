from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from langgraph.types import Command

from agentic_bi_copilot.agent.graph import get_agent_graph
from agentic_bi_copilot.schemas import (
    AgentApprovalResponse,
    AgentDecisionRequest,
    AgentResultResponse,
    AgentResumeResponse,
    AgentRetryResponse,
    AgentRunDetailResponse,
    AgentRunHistoryResponse,
    AgentRunSummaryResponse,
    AgentStartResponse,
    DeclineFindingResponse,
    ManualQueryResponse,
    QueryRequest,
    SQLSafetyResponse,
)
from agentic_bi_copilot.services.exports import (
    ExportDataError,
    build_csv_export,
    build_json_export,
)
from agentic_bi_copilot.services.manual_pipeline import (
    ManualPipelineResult,
    UnsupportedQuestionError,
    run_manual_pipeline,
)
from agentic_bi_copilot.services.run_history import (
    RunHistoryRecord,
    create_run,
    get_run,
    list_runs,
    update_run,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["analytics"],
)


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
            previous_month_revenue=finding.previous_month_revenue,
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
        top_region_revenue=result.analysis.top_region_revenue,
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The approval request was not a valid object.",
        )

    return AgentApprovalResponse.model_validate(approval_value)


def _build_run_summary(
    record: RunHistoryRecord,
) -> AgentRunSummaryResponse:
    """Convert a stored run into a history summary."""

    return AgentRunSummaryResponse(
        thread_id=record.thread_id,
        question=record.question,
        status=record.status,
        source_thread_id=record.source_thread_id,
        has_result=record.result is not None,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _build_export_filename(
    thread_id: str,
    extension: str,
) -> str:
    """Create a safe filename for a downloaded result."""

    safe_thread_id = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in thread_id
    )

    return f"analysis-{safe_thread_id}.{extension}"


def _start_agent_workflow(
    question: str,
    source_thread_id: str | None = None,
) -> AgentStartResponse:
    """Create, run, and store a workflow waiting for approval."""

    thread_id = str(uuid4())

    create_run(
        thread_id=thread_id,
        question=question,
        status="awaiting_approval",
        source_thread_id=source_thread_id,
    )

    graph = get_agent_graph()
    config = _create_graph_config(thread_id)

    state = graph.invoke(
        {
            "question": question,
        },
        config=config,
    )

    approval = _get_approval_request(state)

    if approval is None:
        error = state.get("error") or "The workflow ended before requesting approval."

        update_run(
            thread_id=thread_id,
            status="failed",
            error=error,
        )

        return AgentStartResponse(
            thread_id=thread_id,
            status="failed",
            error=error,
        )

    # Save the approval request so it can be reopened later.
    update_run(
        thread_id=thread_id,
        status="awaiting_approval",
        approval=approval.model_dump(mode="json"),
    )

    return AgentStartResponse(
        thread_id=thread_id,
        status="awaiting_approval",
        approval=approval,
    )


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

    return _start_agent_workflow(request.question)


@router.get(
    "/agent/runs/history",
    response_model=AgentRunHistoryResponse,
)
def get_agent_run_history(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
) -> AgentRunHistoryResponse:
    """Return recent agent runs."""

    records = list_runs(limit=limit)
    summaries = [_build_run_summary(record) for record in records]

    return AgentRunHistoryResponse(
        runs=summaries,
        total=len(summaries),
    )


@router.get(
    "/agent/runs/{thread_id}",
    response_model=AgentRunDetailResponse,
)
def get_agent_run_detail(
    thread_id: str,
) -> AgentRunDetailResponse:
    """Return one stored agent run."""

    record = get_run(thread_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run was not found.",
        )

    summary = _build_run_summary(record)

    return AgentRunDetailResponse(
        **summary.model_dump(),
        result=record.result,
        approval=record.approval,
    )


@router.post(
    "/agent/runs/{thread_id}/retry",
    response_model=AgentRetryResponse,
)
def retry_agent_run(
    thread_id: str,
) -> AgentRetryResponse:
    """Start a new run using an earlier question."""

    record = get_run(thread_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run was not found.",
        )

    if record.status == "awaiting_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("This run is still awaiting approval and cannot be retried yet."),
        )

    response = _start_agent_workflow(
        question=record.question,
        source_thread_id=thread_id,
    )

    return AgentRetryResponse(
        **response.model_dump(),
        source_thread_id=thread_id,
    )


@router.get(
    "/agent/runs/{thread_id}/export",
    response_class=Response,
)
def export_agent_run(
    thread_id: str,
    file_format: Literal["json", "csv"] = Query(
        default="json",
        alias="format",
    ),
) -> Response:
    """Download a completed analysis as JSON or CSV."""

    record = get_run(thread_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run was not found.",
        )

    if record.status != "completed" or record.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed agent runs can be exported.",
        )

    if file_format == "json":
        content = build_json_export(record)
        media_type = "application/json"
    else:
        try:
            content = build_csv_export(record.result)
        except ExportDataError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error

        media_type = "text/csv"

    filename = _build_export_filename(
        thread_id,
        file_format,
    )

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": (f'attachment; filename="{filename}"')},
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

    history_record = get_run(thread_id)

    if history_record is None or history_record.status != "awaiting_approval":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run was not found or is no longer active.",
        )

    graph = get_agent_graph()
    config = _create_graph_config(thread_id)

    state = graph.invoke(
        Command(
            resume={
                "approved": request.approved,
                "feedback": request.feedback,
            }
        ),
        config=config,
    )

    if not request.approved:
        error = (
            state.get("rejection_reason")
            or state.get("error")
            or "The query was rejected."
        )

        update_run(
            thread_id=thread_id,
            status="rejected",
            error=error,
        )

        return AgentResumeResponse(
            thread_id=thread_id,
            status="rejected",
            approved=False,
            error=error,
        )

    if state.get("error"):
        error = str(state["error"])

        update_run(
            thread_id=thread_id,
            status="failed",
            error=error,
        )

        return AgentResumeResponse(
            thread_id=thread_id,
            status="failed",
            approved=True,
            error=error,
        )

    result = build_agent_result(state)

    update_run(
        thread_id=thread_id,
        status="completed",
        result=result.model_dump(mode="json"),
    )

    return AgentResumeResponse(
        thread_id=thread_id,
        status="completed",
        approved=True,
        result=result,
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
