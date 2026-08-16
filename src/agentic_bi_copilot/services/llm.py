from functools import lru_cache

from openai import OpenAI

from agentic_bi_copilot.config import get_settings
from agentic_bi_copilot.schemas import AnalysisPlan, SQLDraft

PLANNER_SYSTEM_PROMPT = """
You are the planning component of a business intelligence copilot.

Your job is to convert a user's business question into a clear analysis plan.

Rules:
- Do not generate SQL.
- Do not execute queries.
- Use only tables provided in the database context.
- Describe analytical steps in business language.
- Include important business-rule and date assumptions.
- Set needs_clarification to true only when ambiguity could materially change
  the result.
- When clarification is unnecessary, clarification_question must be null.
- When a comparison needs a previous period, include that lookback period in
  the plan and exclude it only from the final displayed result.
""".strip()


SQL_GENERATOR_SYSTEM_PROMPT = """
You are the SQL drafting component of a secure business intelligence copilot.

Generate PostgreSQL that answers the supplied business question and follows
the approved analysis plan.

Security requirements:
- Return exactly one read-only SELECT statement.
- Common table expressions are allowed.
- Never use INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP, TRUNCATE,
  COPY, GRANT, REVOKE, transaction control, or stored procedures.
- Use only tables and columns included in the database context.
- The outermost query must include LIMIT 500 or less.
- Return raw SQL without Markdown fences or explanatory comments.

Correctness requirements:
- Follow every business rule in the database context.
- Use explicit date boundaries instead of CURRENT_DATE.
- Use NULLIF when calculating percentages to prevent division by zero.
- When a calculation needs the preceding period, load that period internally
  but exclude it from the final requested date range.
- Use clear snake_case column aliases.
Month-over-month requirements:
- Aggregate one complete calendar month before the requested output range.
- Compute LAG across the lookback month and requested months.
- Filter to the requested output range only after calculating LAG.
- Express month-over-month change in percentage points, rounded to two
  decimal places, using:
  ROUND(
      100.0 * (revenue - previous_month_revenue)
      / NULLIF(previous_month_revenue, 0),
      2
  )
- Compare the unusual-decline threshold with -25.0 percentage points,
  not with the decimal ratio -0.25.
- For the six-month regional revenue analysis, aggregate from 2026-01-01
  through 2026-07-31, calculate LAG, and return only 2026-02-01 through
  2026-07-31.
For regional monthly revenue analysis, return these columns in this order:
month, region, revenue, previous_month_revenue,
month_over_month_change_pct, unusual_decline.
""".strip()


@lru_cache
def get_openai_client() -> OpenAI:
    """Create and reuse the OpenAI client."""
    settings = get_settings()

    return OpenAI(
        api_key=settings.openai_api_key,
    )


def _clean_question(question: str) -> str:
    """Remove extra spacing and reject an empty question."""
    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError("Question cannot be empty.")

    return cleaned_question


def _build_messages(
    system_prompt: str,
    user_prompt: str,
) -> list[dict[str, str]]:
    """Build the system and user messages sent to the model."""
    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def _build_planner_prompt(
    question: str,
    schema_context: str,
) -> str:
    """Build the user prompt for analysis planning."""
    return f"Business question:\n{question}\n\nDatabase context:\n{schema_context}"


def _build_sql_prompt(
    question: str,
    plan: AnalysisPlan,
    schema_context: str,
) -> str:
    """Build the user prompt for SQL generation."""
    return (
        f"Business question:\n{question}\n\n"
        f"Approved analysis plan:\n"
        f"{plan.model_dump_json(indent=2)}\n\n"
        f"Database context:\n{schema_context}"
    )


def create_analysis_plan(
    question: str,
    schema_context: str,
) -> AnalysisPlan:
    """Ask the model to create a structured analysis plan."""
    cleaned_question = _clean_question(question)
    settings = get_settings()
    client = get_openai_client()

    user_prompt = _build_planner_prompt(
        cleaned_question,
        schema_context,
    )
    messages = _build_messages(
        PLANNER_SYSTEM_PROMPT,
        user_prompt,
    )

    response = client.responses.parse(
        model=settings.model_name,
        input=messages,
        text_format=AnalysisPlan,
    )

    plan = response.output_parsed

    if plan is None:
        raise RuntimeError("The model did not return a valid analysis plan.")

    return plan


def generate_sql(
    question: str,
    plan: AnalysisPlan,
    schema_context: str,
) -> SQLDraft:
    """Ask the model to create a structured SQL draft."""
    cleaned_question = _clean_question(question)

    if plan.needs_clarification:
        raise ValueError(
            "SQL cannot be generated until the requested clarification is resolved."
        )

    settings = get_settings()
    client = get_openai_client()

    user_prompt = _build_sql_prompt(
        cleaned_question,
        plan,
        schema_context,
    )
    messages = _build_messages(
        SQL_GENERATOR_SYSTEM_PROMPT,
        user_prompt,
    )

    response = client.responses.parse(
        model=settings.model_name,
        input=messages,
        text_format=SQLDraft,
    )

    draft = response.output_parsed

    if draft is None:
        raise RuntimeError("The model did not return a valid SQL draft.")

    return draft
