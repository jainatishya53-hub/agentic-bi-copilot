from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["healthy"]


class QueryRequest(BaseModel):
    question: str = Field(
        min_length=10,
        max_length=500,
    )


class SQLSafetyResponse(BaseModel):
    is_safe: bool
    referenced_tables: list[str]
    checks: list[str]
    errors: list[str]


class DeclineFindingResponse(BaseModel):
    region: str
    month: date
    revenue: Decimal
    previous_month_revenue: Decimal
    change_pct: Decimal


class ManualQueryResponse(BaseModel):
    mode: Literal["manual"] = "manual"
    question: str
    analysis_plan: list[str]
    selected_tables: list[str]
    sql: str
    safety: SQLSafetyResponse
    columns: list[str]
    rows: list[dict[str, Any]]
    total_revenue: Decimal
    top_region: str
    top_region_revenue: Decimal
    findings: list[DeclineFindingResponse]
    chart: dict[str, Any]
    answer: str
    follow_up_questions: list[str]
    execution_time_ms: float


class AnalysisPlan(BaseModel):
    interpreted_question: str
    required_tables: list[str]
    steps: list[str]
    assumptions: list[str]
    needs_clarification: bool
    clarification_question: str | None


class SQLDraft(BaseModel):
    sql: str
    explanation: str
    referenced_tables: list[str]

class AgentApprovalResponse(BaseModel):
    question: str
    sql: str
    sql_explanation: str
    referenced_tables: list[str]
    validation: dict[str, Any]


class AgentStartResponse(BaseModel):
    thread_id: str
    status: Literal["awaiting_approval", "failed"]
    approval: AgentApprovalResponse | None = None
    error: str | None = None


class AgentDecisionRequest(BaseModel):
    approved: bool
    feedback: str | None = Field(
        default=None,
        max_length=500,
    )


class AgentResultResponse(BaseModel):
    question: str
    plan: dict[str, Any]
    sql: str
    sql_explanation: str
    referenced_tables: list[str]
    validation: dict[str, Any]
    query_result: dict[str, Any]
    analysis: dict[str, Any]
    answer: str
    chart: dict[str, Any]


class AgentResumeResponse(BaseModel):
    thread_id: str
    status: Literal["completed", "rejected", "failed"]
    approved: bool
    result: AgentResultResponse | None = None
    error: str | None = None