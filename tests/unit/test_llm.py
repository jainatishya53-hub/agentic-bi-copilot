from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from agentic_bi_copilot.schemas import AnalysisPlan
from agentic_bi_copilot.services.llm import create_analysis_plan


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