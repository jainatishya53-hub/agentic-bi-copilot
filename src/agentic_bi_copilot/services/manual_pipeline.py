import re
from dataclasses import dataclass
from typing import Any

from agentic_bi_copilot.database.query_service import (
    execute_validated_query,
)
from agentic_bi_copilot.security.sql_validator import (
    SQLValidationResult,
)
from agentic_bi_copilot.services.analysis import (
    RevenueAnalysis,
    analyze_regional_revenue,
)
from agentic_bi_copilot.services.charts import (
    chart_to_spec,
    create_regional_revenue_chart,
)

PRIMARY_QUESTION = (
    "Compare revenue across regions for the last six complete months, "
    "identify unusual declines, and generate a suitable chart."
)


PRIMARY_QUERY = """
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', o.order_date)::date AS month,
        r.name AS region,
        ROUND(
            SUM(oi.quantity * oi.unit_price),
            2
        ) AS revenue
    FROM orders AS o
    JOIN customers AS c
        ON c.customer_id = o.customer_id
    JOIN regions AS r
        ON r.region_id = c.region_id
    JOIN order_items AS oi
        ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
      AND o.order_date >= DATE '2026-01-01'
      AND o.order_date < DATE '2026-08-01'
    GROUP BY
        DATE_TRUNC('month', o.order_date)::date,
        r.name
),
revenue_with_previous_month AS (
    SELECT
        month,
        region,
        revenue,
        LAG(revenue) OVER (
            PARTITION BY region
            ORDER BY month
        ) AS previous_month_revenue
    FROM monthly_revenue
),
calculated_changes AS (
    SELECT
        month,
        region,
        revenue,
        previous_month_revenue,
        ROUND(
            (
                (revenue - previous_month_revenue)
                / NULLIF(previous_month_revenue, 0)
            ) * 100,
            2
        ) AS month_over_month_change_pct
    FROM revenue_with_previous_month
)
SELECT
    month,
    region,
    revenue,
    previous_month_revenue,
    month_over_month_change_pct,
    month_over_month_change_pct <= -20 AS unusual_decline
FROM calculated_changes
WHERE month >= DATE '2026-02-01'
ORDER BY
    region,
    month
LIMIT 500
"""


ANALYSIS_PLAN = (
    "Use completed orders from January through July 2026.",
    "Calculate monthly revenue for each region.",
    "Return February through July as the six complete months.",
    "Calculate month-over-month revenue changes.",
    "Flag declines of 20% or more.",
    "Render a multi-series line chart.",
)


SELECTED_TABLES = (
    "customers",
    "order_items",
    "orders",
    "regions",
)


FOLLOW_UP_QUESTIONS = (
    "Which products contributed most to the largest decline?",
    "How did each region perform against its monthly target?",
    "Which customer segments changed most during these months?",
)


class UnsupportedQuestionError(ValueError):
    """Raised when the manual pipeline cannot answer a question."""


@dataclass(frozen=True, slots=True)
class ManualPipelineResult:
    """Store the complete result of the manual pipeline."""

    question: str
    analysis_plan: tuple[str, ...]
    selected_tables: tuple[str, ...]
    sql: str
    validation: SQLValidationResult
    columns: list[str]
    rows: list[dict[str, Any]]
    analysis: RevenueAnalysis
    chart: dict[str, Any]
    answer: str
    follow_up_questions: tuple[str, ...]
    execution_time_ms: float


def _get_question_words(question: str) -> set[str]:
    """Convert a question into a set of simple lowercase words."""
    normalized_question = re.sub(
        r"[^a-z0-9\s]",
        " ",
        question.lower(),
    )

    return set(normalized_question.split())


def supports_primary_question(question: str) -> bool:
    """Check whether the manual pipeline supports the question."""
    words = _get_question_words(question)

    has_revenue = "revenue" in words
    has_six = "six" in words
    has_region = any(word.startswith("region") for word in words)
    has_month = any(word.startswith("month") for word in words)
    has_decline = any(word.startswith("declin") for word in words)

    return has_revenue and has_six and has_region and has_month and has_decline


def create_business_answer(analysis: RevenueAnalysis) -> str:
    """Create a readable summary of the revenue analysis."""
    largest_decline = analysis.unusual_declines[0]
    decline_count = len(analysis.unusual_declines)

    return (
        f"{analysis.top_region} generated the highest revenue across "
        f"the six-month period at "
        f"${analysis.top_region_revenue:,.2f}. "
        f"{decline_count} unusual monthly declines were detected. "
        f"The largest occurred in {largest_decline.region} during "
        f"{largest_decline.month:%B %Y}, when revenue fell "
        f"{abs(largest_decline.change_pct):.2f}% to "
        f"${largest_decline.revenue:,.2f}."
    )


def run_manual_pipeline(question: str) -> ManualPipelineResult:
    """Run the deterministic regional revenue pipeline."""
    if not supports_primary_question(question):
        raise UnsupportedQuestionError(
            "The manual MVP currently supports only regional revenue "
            "comparison for the last six complete months."
        )

    # Validate the fixed SQL before executing it.
    execution = execute_validated_query(PRIMARY_QUERY)
    query_result = execution.query_result

    analysis = analyze_regional_revenue(query_result.rows)

    figure = create_regional_revenue_chart(
        query_result.rows,
        analysis,
    )
    chart = chart_to_spec(figure)
    answer = create_business_answer(analysis)

    return ManualPipelineResult(
        question=question,
        analysis_plan=ANALYSIS_PLAN,
        selected_tables=SELECTED_TABLES,
        sql=execution.validation.normalized_sql or PRIMARY_QUERY,
        validation=execution.validation,
        columns=query_result.columns,
        rows=query_result.rows,
        analysis=analysis,
        chart=chart,
        answer=answer,
        follow_up_questions=FOLLOW_UP_QUESTIONS,
        execution_time_ms=query_result.execution_time_ms,
    )
