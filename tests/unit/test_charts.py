import json
from datetime import date
from decimal import Decimal

import pytest

from agentic_bi_copilot.services.analysis import (
    analyze_regional_revenue,
)
from agentic_bi_copilot.services.charts import (
    chart_to_spec,
    create_regional_revenue_chart,
)

SAMPLE_ROWS = [
    {
        "month": date(2026, 6, 1),
        "region": "North",
        "revenue": Decimal("100.00"),
        "previous_month_revenue": Decimal("90.00"),
    },
    {
        "month": date(2026, 7, 1),
        "region": "North",
        "revenue": Decimal("120.00"),
        "previous_month_revenue": Decimal("100.00"),
    },
    {
        "month": date(2026, 6, 1),
        "region": "South",
        "revenue": Decimal("100.00"),
        "previous_month_revenue": Decimal("95.00"),
    },
    {
        "month": date(2026, 7, 1),
        "region": "South",
        "revenue": Decimal("50.00"),
        "previous_month_revenue": Decimal("100.00"),
    },
]


def test_creates_line_chart_with_decline_markers() -> None:
    analysis = analyze_regional_revenue(SAMPLE_ROWS)

    figure = create_regional_revenue_chart(
        SAMPLE_ROWS,
        analysis,
    )

    trace_names = {
        trace.name
        for trace in figure.data
    }

    assert trace_names == {
        "North",
        "South",
        "Unusual decline",
    }
    assert figure.layout.title.text == "Monthly Revenue by Region"

    decline_trace = next(
        trace
        for trace in figure.data
        if trace.name == "Unusual decline"
    )

    assert len(decline_trace.x) == 1
    assert decline_trace.text[0] == "South"


def test_produces_json_serializable_chart_specification() -> None:
    analysis = analyze_regional_revenue(SAMPLE_ROWS)
    figure = create_regional_revenue_chart(
        SAMPLE_ROWS,
        analysis,
    )

    chart_specification = chart_to_spec(figure)

    assert "data" in chart_specification
    assert "layout" in chart_specification
    json.dumps(chart_specification)


def test_rejects_empty_chart_data() -> None:
    analysis = analyze_regional_revenue(SAMPLE_ROWS)

    with pytest.raises(
        ValueError,
        match="Cannot create a chart from an empty result",
    ):
        create_regional_revenue_chart([], analysis)