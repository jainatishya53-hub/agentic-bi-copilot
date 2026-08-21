from unittest.mock import patch

from agentic_bi_copilot.agent.nodes import (
    analysis_node,
    chart_node,
)
from agentic_bi_copilot.schemas import (
    ChartRecommendation,
    QueryResultAnalysis,
)


def create_generic_analysis() -> QueryResultAnalysis:
    """Create a general analysis used by the tests."""

    return QueryResultAnalysis(
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
            title="Top Products by Revenue",
            x_column="product",
            y_column="revenue",
            color_column=None,
        ),
    )


def test_analysis_node_uses_generic_result_analysis() -> None:
    analysis = create_generic_analysis()
    rows = [
        {
            "product": "Laptop",
            "revenue": 50000.0,
        }
    ]
    state = {
        "question": "Which products generated the most revenue?",
        "query_result": {
            "columns": ["product", "revenue"],
            "rows": rows,
        },
    }

    with patch(
        "agentic_bi_copilot.agent.nodes.create_query_result_analysis",
        return_value=analysis,
    ) as create_analysis:
        result = analysis_node(state)

    create_analysis.assert_called_once_with(
        question=state["question"],
        columns=["product", "revenue"],
        rows=rows,
    )

    assert result["analysis"] == analysis.model_dump(mode="json")
    assert result["answer"] == analysis.answer
    assert result["follow_up_questions"] == ["How did Laptop perform by region?"]
    assert result["error"] is None


def test_chart_node_uses_generic_chart_recommendation() -> None:
    analysis = create_generic_analysis()
    rows = [
        {
            "product": "Laptop",
            "revenue": 50000.0,
        }
    ]
    fake_figure = object()
    fake_chart = {
        "data": [{"type": "bar"}],
        "layout": {"title": "Top Products by Revenue"},
    }
    state = {
        "question": "Which products generated the most revenue?",
        "query_result": {
            "columns": ["product", "revenue"],
            "rows": rows,
        },
        "analysis": analysis.model_dump(mode="json"),
    }

    with (
        patch(
            "agentic_bi_copilot.agent.nodes.create_query_result_chart",
            return_value=fake_figure,
        ) as create_chart,
        patch(
            "agentic_bi_copilot.agent.nodes.chart_to_spec",
            return_value=fake_chart,
        ) as create_spec,
    ):
        result = chart_node(state)

    create_chart.assert_called_once_with(
        rows,
        analysis.chart,
    )
    create_spec.assert_called_once_with(fake_figure)

    assert result["chart"] == fake_chart
    assert result["error"] is None


def test_regional_columns_keep_deterministic_analysis() -> None:
    rows = [
        {
            "month": "2026-02-01",
            "region": "North",
            "revenue": 50000.0,
            "previous_month_revenue": 48000.0,
            "month_over_month_change_pct": 4.17,
            "unusual_decline": False,
        }
    ]
    state = {
        "question": "Compare regional revenue.",
        "query_result": {
            "columns": [
                "month",
                "region",
                "revenue",
                "previous_month_revenue",
                "month_over_month_change_pct",
                "unusual_decline",
            ],
            "rows": rows,
        },
    }

    with (
        patch(
            "agentic_bi_copilot.agent.nodes.analyze_regional_revenue"
        ) as regional_analysis,
        patch(
            "agentic_bi_copilot.agent.nodes.create_business_answer",
            return_value="Regional answer.",
        ),
        patch(
            "agentic_bi_copilot.agent.nodes.create_query_result_analysis"
        ) as generic_analysis,
    ):
        regional_analysis.return_value = {"top_region": "North"}
        result = analysis_node(state)

    regional_analysis.assert_called_once()
    generic_analysis.assert_not_called()
    assert result["answer"] == "Regional answer."
