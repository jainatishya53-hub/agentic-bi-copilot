from fastapi import APIRouter, HTTPException, status

from agentic_bi_copilot.schemas import (
    DeclineFindingResponse,
    ManualQueryResponse,
    QueryRequest,
    SQLSafetyResponse,
)
from agentic_bi_copilot.services.manual_pipeline import (
    UnsupportedQuestionError,
    run_manual_pipeline,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["analytics"],
)


@router.post(
    "/manual-query",
    response_model=ManualQueryResponse,
)
def manual_query(request: QueryRequest) -> ManualQueryResponse:
    try:
        result = run_manual_pipeline(request.question)
    except UnsupportedQuestionError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return ManualQueryResponse(
        question=result.question,
        analysis_plan=list(result.analysis_plan),
        selected_tables=list(result.selected_tables),
        sql=result.sql,
        safety=SQLSafetyResponse(
            is_safe=result.validation.is_safe,
            referenced_tables=list(
                result.validation.referenced_tables
            ),
            checks=list(result.validation.checks),
            errors=list(result.validation.errors),
        ),
        columns=result.columns,
        rows=result.rows,
        total_revenue=result.analysis.total_revenue,
        top_region=result.analysis.top_region,
        top_region_revenue=result.analysis.top_region_revenue,
        findings=[
            DeclineFindingResponse(
                region=finding.region,
                month=finding.month,
                revenue=finding.revenue,
                previous_month_revenue=(
                    finding.previous_month_revenue
                ),
                change_pct=finding.change_pct,
            )
            for finding in result.analysis.unusual_declines
        ],
        chart=result.chart,
        answer=result.answer,
        follow_up_questions=list(
            result.follow_up_questions
        ),
        execution_time_ms=result.execution_time_ms,
    )