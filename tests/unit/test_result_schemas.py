import pytest
from pydantic import ValidationError

from agentic_bi_copilot.schemas import (
    ChartRecommendation,
    QueryResultAnalysis,
)


def create_valid_analysis() -> QueryResultAnalysis:
    """Create a valid result used by the tests."""

    return QueryResultAnalysis(
        analysis_type="ranking",
        answer="Product A generated the highest revenue.",
        key_findings=[
            "Product A generated $50,000 in revenue.",
            "Product B ranked second with $42,000.",
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


def test_creates_structured_result_analysis() -> None:
    analysis = create_valid_analysis()

    assert analysis.analysis_type == "ranking"
    assert analysis.chart.chart_type == "bar"
    assert analysis.chart.x_column == "product"
    assert len(analysis.key_findings) == 2


def test_allows_table_without_chart_columns() -> None:
    chart = ChartRecommendation(
        chart_type="table",
        title="Query Results",
        x_column=None,
        y_column=None,
        color_column=None,
    )

    assert chart.chart_type == "table"
    assert chart.x_column is None
    assert chart.y_column is None


def test_rejects_unknown_analysis_type() -> None:
    with pytest.raises(ValidationError):
        QueryResultAnalysis(
            analysis_type="unsupported",
            answer="Test answer.",
            key_findings=["Test finding."],
            follow_up_questions=["What should we examine next?"],
            chart=ChartRecommendation(
                chart_type="table",
                title="Test Results",
                x_column=None,
                y_column=None,
                color_column=None,
            ),
        )


def test_rejects_unknown_chart_type() -> None:
    with pytest.raises(ValidationError):
        ChartRecommendation(
            chart_type="pie",
            title="Invalid Chart",
            x_column="category",
            y_column="revenue",
            color_column=None,
        )


def test_limits_follow_up_questions() -> None:
    with pytest.raises(ValidationError):
        QueryResultAnalysis(
            analysis_type="general",
            answer="Test answer.",
            key_findings=["Test finding."],
            follow_up_questions=[
                "Question one?",
                "Question two?",
                "Question three?",
                "Question four?",
            ],
            chart=ChartRecommendation(
                chart_type="table",
                title="Test Results",
                x_column=None,
                y_column=None,
                color_column=None,
            ),
        )
