from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from agentic_bi_copilot.schemas import AnalysisPlan, SQLDraft
from agentic_bi_copilot.services.llm import (
    PLANNER_SYSTEM_PROMPT,
    SQL_GENERATOR_SYSTEM_PROMPT,
    create_analysis_plan,
    generate_sql,
)


def test_create_analysis_plan_returns_structured_plan() -> None:
    expected_plan = AnalysisPlan(
        interpreted_question="Compare regional revenue for six months.",
        required_tables=[
            "regions",
            "customers",
            "orders",
            "order_items",
        ],
        steps=[
            "Calculate monthly completed-order revenue by region.",
            "Compare each month with the previous month.",
            "Identify unusual declines.",
        ],
        assumptions=[
            "Revenue uses completed orders only.",
            "Use the last six complete months.",
        ],
        needs_clarification=False,
        clarification_question=None,
    )

    fake_client = Mock()
    fake_client.responses.parse.return_value = SimpleNamespace(
        output_parsed=expected_plan
    )

    fake_settings = SimpleNamespace(model_name="test-model")

    with (
        patch(
            "agentic_bi_copilot.services.llm.get_openai_client",
            return_value=fake_client,
        ),
        patch(
            "agentic_bi_copilot.services.llm.get_settings",
            return_value=fake_settings,
        ),
    ):
        result = create_analysis_plan(
            question="Compare regional revenue.",
            schema_context="Available table: regions",
        )

    assert result == expected_plan

    call_arguments = fake_client.responses.parse.call_args.kwargs
    assert call_arguments["model"] == "test-model"
    assert call_arguments["text_format"] is AnalysisPlan
    assert "Compare regional revenue." in call_arguments["input"][1]["content"]


def test_create_analysis_plan_rejects_empty_question() -> None:
    with pytest.raises(ValueError, match="Question cannot be empty"):
        create_analysis_plan(
            question="   ",
            schema_context="Available table: regions",
        )


def test_create_analysis_plan_rejects_missing_parsed_output() -> None:
    fake_client = Mock()
    fake_client.responses.parse.return_value = SimpleNamespace(
        output_parsed=None
    )

    fake_settings = SimpleNamespace(model_name="test-model")

    with (
        patch(
            "agentic_bi_copilot.services.llm.get_openai_client",
            return_value=fake_client,
        ),
        patch(
            "agentic_bi_copilot.services.llm.get_settings",
            return_value=fake_settings,
        ),
        pytest.raises(RuntimeError, match="valid analysis plan"),
    ):
        create_analysis_plan(
            question="Compare regional revenue.",
            schema_context="Available table: regions",
        )


def test_generate_sql_returns_structured_draft() -> None:
    plan = AnalysisPlan(
        interpreted_question="Compare regional revenue.",
        required_tables=[
            "regions",
            "customers",
            "orders",
            "order_items",
        ],
        steps=["Calculate monthly revenue by region."],
        assumptions=["Completed orders count toward revenue."],
        needs_clarification=False,
        clarification_question=None,
    )

    expected_draft = SQLDraft(
        sql="SELECT name AS region FROM regions ORDER BY name LIMIT 10",
        explanation="Lists the available regions.",
        referenced_tables=["regions"],
    )

    fake_client = Mock()
    fake_client.responses.parse.return_value = SimpleNamespace(
        output_parsed=expected_draft
    )

    fake_settings = SimpleNamespace(model_name="test-model")

    with (
        patch(
            "agentic_bi_copilot.services.llm.get_openai_client",
            return_value=fake_client,
        ),
        patch(
            "agentic_bi_copilot.services.llm.get_settings",
            return_value=fake_settings,
        ),
    ):
        result = generate_sql(
            question="Compare regional revenue.",
            plan=plan,
            schema_context="Available table: regions",
        )

    assert result == expected_draft

    call_arguments = fake_client.responses.parse.call_args.kwargs
    assert call_arguments["model"] == "test-model"
    assert call_arguments["text_format"] is SQLDraft
    assert "Approved analysis plan" in call_arguments["input"][1]["content"]


def test_generate_sql_requires_resolved_clarification() -> None:
    plan = AnalysisPlan(
        interpreted_question="Compare revenue.",
        required_tables=["orders", "order_items"],
        steps=["Calculate revenue."],
        assumptions=[],
        needs_clarification=True,
        clarification_question="Which date range should be used?",
    )

    with pytest.raises(ValueError, match="clarification"):
        generate_sql(
            question="Compare revenue.",
            plan=plan,
            schema_context="Available table: orders",
        )


def test_generate_sql_rejects_missing_parsed_output() -> None:
    plan = AnalysisPlan(
        interpreted_question="Compare regional revenue.",
        required_tables=["regions"],
        steps=["List regions."],
        assumptions=[],
        needs_clarification=False,
        clarification_question=None,
    )

    fake_client = Mock()
    fake_client.responses.parse.return_value = SimpleNamespace(
        output_parsed=None
    )

    fake_settings = SimpleNamespace(model_name="test-model")

    with (
        patch(
            "agentic_bi_copilot.services.llm.get_openai_client",
            return_value=fake_client,
        ),
        patch(
            "agentic_bi_copilot.services.llm.get_settings",
            return_value=fake_settings,
        ),
        pytest.raises(RuntimeError, match="valid SQL draft"),
    ):
        generate_sql(
            question="Compare regional revenue.",
            plan=plan,
            schema_context="Available table: regions",
        )


def test_llm_prompts_define_month_over_month_semantics() -> None:
    assert "lookback period" in PLANNER_SYSTEM_PROMPT
    assert "Compute LAG" in SQL_GENERATOR_SYSTEM_PROMPT
    assert "100.0 *" in SQL_GENERATOR_SYSTEM_PROMPT
    assert "-25.0 percentage points" in SQL_GENERATOR_SYSTEM_PROMPT
    assert "2026-01-01" in SQL_GENERATOR_SYSTEM_PROMPT