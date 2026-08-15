from typing import TypedDict


class AgentState(TypedDict, total=False):
    question: str
    schema_context: str
    plan: dict[str, object]
    sql: str
    sql_explanation: str
    referenced_tables: list[str]
    validation: dict[str, object]
    approved: bool
    rejection_reason: str | None
    error: str | None
    query_result: dict[str, object]
    analysis: dict[str, object]
    answer: str
    follow_up_questions: list[str]
    chart: dict[str, object]
