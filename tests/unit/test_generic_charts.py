from decimal import Decimal

from agentic_bi_copilot.schemas import ChartRecommendation
from agentic_bi_copilot.services.charts import (
    create_query_result_chart,
)


def test_creates_time_series_line_chart() -> None:
    recommendation = ChartRecommendation(
        chart_type="line",
        title="Monthly Revenue",
        x_column="month",
        y_column="revenue",
        color_column=None,
    )
    rows = [
        {
            "month": "2026-06-01",
            "revenue": Decimal("1000.00"),
        },
        {
            "month": "2026-07-01",
            "revenue": Decimal("1200.00"),
        },
    ]

    figure = create_query_result_chart(
        rows,
        recommendation,
    )

    assert len(figure.data) == 1
    assert figure.data[0].type == "scatter"
    assert figure.layout.title.text == "Monthly Revenue"


def test_creates_ranking_bar_chart() -> None:
    recommendation = ChartRecommendation(
        chart_type="bar",
        title="Top Products",
        x_column="product",
        y_column="revenue",
        color_column=None,
    )
    rows = [
        {
            "product": "Laptop",
            "revenue": Decimal("50000.00"),
        },
        {
            "product": "Monitor",
            "revenue": Decimal("42000.00"),
        },
    ]

    figure = create_query_result_chart(
        rows,
        recommendation,
    )

    assert len(figure.data) == 1
    assert figure.data[0].type == "bar"
    assert list(figure.data[0].x) == [
        "Laptop",
        "Monitor",
    ]


def test_creates_grouped_bar_chart() -> None:
    recommendation = ChartRecommendation(
        chart_type="grouped_bar",
        title="Actual Revenue and Target",
        x_column="region",
        y_column="amount",
        color_column="measure",
    )
    rows = [
        {
            "region": "North",
            "measure": "Actual",
            "amount": Decimal("50000.00"),
        },
        {
            "region": "North",
            "measure": "Target",
            "amount": Decimal("48000.00"),
        },
        {
            "region": "South",
            "measure": "Actual",
            "amount": Decimal("42000.00"),
        },
        {
            "region": "South",
            "measure": "Target",
            "amount": Decimal("45000.00"),
        },
    ]

    figure = create_query_result_chart(
        rows,
        recommendation,
    )

    assert len(figure.data) == 2
    assert all(trace.type == "bar" for trace in figure.data)
    assert figure.layout.barmode == "group"


def test_creates_table_chart() -> None:
    recommendation = ChartRecommendation(
        chart_type="table",
        title="Customer Results",
        x_column=None,
        y_column=None,
        color_column=None,
    )
    rows = [
        {
            "customer": "Customer 1",
            "revenue": Decimal("25000.00"),
        }
    ]

    figure = create_query_result_chart(
        rows,
        recommendation,
    )

    assert len(figure.data) == 1
    assert figure.data[0].type == "table"


def test_invalid_columns_fall_back_to_table() -> None:
    recommendation = ChartRecommendation(
        chart_type="bar",
        title="Invalid Recommendation",
        x_column="product",
        y_column="profit",
        color_column=None,
    )
    rows = [
        {
            "product": "Laptop",
            "revenue": Decimal("50000.00"),
        }
    ]

    figure = create_query_result_chart(
        rows,
        recommendation,
    )

    assert figure.data[0].type == "table"


def test_empty_result_creates_message_figure() -> None:
    recommendation = ChartRecommendation(
        chart_type="table",
        title="Empty Result",
        x_column=None,
        y_column=None,
        color_column=None,
    )

    figure = create_query_result_chart(
        [],
        recommendation,
    )

    assert not figure.data
    assert figure.layout.annotations
    assert "No matching data" in figure.layout.annotations[0].text
