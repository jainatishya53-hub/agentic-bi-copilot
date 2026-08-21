from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from agentic_bi_copilot.schemas import (
    ChartRecommendation,
    QueryResultAnalysis,
)
from agentic_bi_copilot.services.llm import (
    create_query_result_analysis,
)


def create_expected_analysis() -> QueryResultAnalysis:
    """Create a valid structured analysis for the tests."""

    return QueryResultAnalysis(
        analysis_type="ranking",
        answer="Laptop generated the highest product revenue.",
        key_findings=[
            "Laptop generated $50,000 in revenue.",
            "Monitor generated $42,000 in revenue.",
        ],
        follow_up_questions=[
            "How did these products perform by region?",
            "How did their revenue change by month?",
        ],
        chart=ChartRecommendation(
            chart_type="bar",
            title="Top Products by Revenue",
            x_column="product",
            y_column="revenue",
            color_column=None,
        ),
    )


def test_creates_grounded_query_result_analysis() -> None:
    expected_analysis = create_expected_analysis()

    fake_client = Mock()
    fake_client.responses.parse.return_value = SimpleNamespace(
        output_parsed=expected_analysis
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
        result = create_query_result_analysis(
            question="Which products generated the most revenue?",
            columns=["product", "revenue"],
            rows=[
                {
                    "product": "Laptop",
                    "revenue": "50000.00",
                },
                {
                    "product": "Monitor",
                    "revenue": "42000.00",
                },
            ],
        )

    assert result == expected_analysis

    call_arguments = fake_client.responses.parse.call_args.kwargs

    assert call_arguments["model"] == "test-model"
    assert call_arguments["text_format"] is QueryResultAnalysis
    assert '"product": "Laptop"' in call_arguments["input"][1]["content"]
    assert "Available columns" in call_arguments["input"][1]["content"]


def test_empty_result_does_not_call_model() -> None:
    with patch("agentic_bi_copilot.services.llm.get_openai_client") as client_factory:
        result = create_query_result_analysis(
            question="Which products generated revenue?",
            columns=["product", "revenue"],
            rows=[],
        )

    client_factory.assert_not_called()

    assert result.analysis_type == "general"
    assert result.chart.chart_type == "table"
    assert "no matching data" in result.answer.lower()


def test_rejects_empty_result_columns() -> None:
    with pytest.raises(
        ValueError,
        match="columns cannot be empty",
    ):
        create_query_result_analysis(
            question="Which products generated revenue?",
            columns=[],
            rows=[],
        )


def test_rejects_missing_parsed_analysis() -> None:
    fake_client = Mock()
    fake_client.responses.parse.return_value = SimpleNamespace(output_parsed=None)
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
        pytest.raises(
            RuntimeError,
            match="valid query result analysis",
        ),
    ):
        create_query_result_analysis(
            question="Which products generated revenue?",
            columns=["product", "revenue"],
            rows=[
                {
                    "product": "Laptop",
                    "revenue": "50000.00",
                }
            ],
        )


def test_invalid_chart_columns_fall_back_to_table() -> None:
    invalid_analysis = QueryResultAnalysis(
        analysis_type="ranking",
        answer="Laptop generated the highest revenue.",
        key_findings=[
            "Laptop generated $50,000 in revenue.",
        ],
        follow_up_questions=[
            "How did Laptop perform by region?",
        ],
        chart=ChartRecommendation(
            chart_type="bar",
            title="Top Products by Profit",
            x_column="product",
            y_column="profit",
            color_column=None,
        ),
    )

    fake_client = Mock()
    fake_client.responses.parse.return_value = SimpleNamespace(
        output_parsed=invalid_analysis
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
        result = create_query_result_analysis(
            question="Which products generated the most revenue?",
            columns=["product", "revenue"],
            rows=[
                {
                    "product": "Laptop",
                    "revenue": "50000.00",
                }
            ],
        )

    assert result.chart.chart_type == "table"
    assert result.chart.x_column is None
    assert result.chart.y_column is None
