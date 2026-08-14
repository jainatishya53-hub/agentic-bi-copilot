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