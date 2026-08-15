from functools import lru_cache

from openai import OpenAI

from agentic_bi_copilot.config import get_settings
from agentic_bi_copilot.schemas import AnalysisPlan

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
""".strip()


@lru_cache
def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)


def create_analysis_plan(
    question: str,
    schema_context: str,
) -> AnalysisPlan:
    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError("Question cannot be empty.")

    settings = get_settings()
    client = get_openai_client()

    response = client.responses.parse(
        model=settings.model_name,
        input=[
            {
                "role": "system",
                "content": PLANNER_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Business question:\n{cleaned_question}\n\n"
                    f"Database context:\n{schema_context}"
                ),
            },
        ],
        text_format=AnalysisPlan,
    )

    plan = response.output_parsed

    if plan is None:
        raise RuntimeError("The model did not return a valid analysis plan.")

    return plan