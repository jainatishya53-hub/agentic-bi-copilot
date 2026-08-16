import json
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from agentic_bi_copilot.services.analysis import (
    RevenueAnalysis,
    as_date,
    as_decimal,
)

REQUIRED_CHART_COLUMNS = {
    "month",
    "region",
    "revenue",
}


def _validate_row(
    row: Mapping[str, Any],
    row_number: int,
) -> None:
    """Check that a row contains the required chart columns."""
    missing_columns = REQUIRED_CHART_COLUMNS - row.keys()

    if missing_columns:
        missing_names = ", ".join(sorted(missing_columns))
        raise ValueError(f"Row {row_number} is missing columns: {missing_names}")


def _create_chart_records(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Convert query rows into records Plotly can use."""
    records: list[dict[str, Any]] = []

    for row_number, row in enumerate(rows, start=1):
        _validate_row(row, row_number)

        records.append(
            {
                "month": as_date(row["month"]),
                "region": str(row["region"]),
                "revenue": float(as_decimal(row["revenue"])),
            }
        )

    return records


def _create_chart_frame(
    records: list[dict[str, Any]],
) -> pd.DataFrame:
    """Create and sort the chart data frame."""
    frame = pd.DataFrame.from_records(records)

    return frame.sort_values(
        ["region", "month"],
        kind="stable",
    )


def _create_line_chart(frame: pd.DataFrame) -> go.Figure:
    """Create the main regional revenue line chart."""
    region_order = sorted(frame["region"].unique().tolist())

    return px.line(
        frame,
        x="month",
        y="revenue",
        color="region",
        markers=True,
        category_orders={"region": region_order},
        title="Monthly Revenue by Region",
        labels={
            "month": "Month",
            "revenue": "Revenue",
            "region": "Region",
        },
    )


def _add_decline_markers(
    figure: go.Figure,
    analysis: RevenueAnalysis,
) -> None:
    """Add red markers for unusual revenue declines."""
    if not analysis.unusual_declines:
        return

    figure.add_trace(
        go.Scatter(
            x=[finding.month for finding in analysis.unusual_declines],
            y=[float(finding.revenue) for finding in analysis.unusual_declines],
            mode="markers",
            name="Unusual decline",
            marker={
                "color": "#D62728",
                "size": 12,
                "symbol": "x",
                "line": {"width": 2},
            },
            text=[finding.region for finding in analysis.unusual_declines],
            customdata=[
                float(finding.change_pct) for finding in analysis.unusual_declines
            ],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "%{x|%b %Y}<br>"
                "Revenue: $%{y:,.2f}<br>"
                "Monthly change: %{customdata:.2f}%"
                "<extra></extra>"
            ),
        )
    )


def _format_chart(figure: go.Figure) -> None:
    """Apply the final layout and axis formatting."""
    figure.update_layout(
        template="plotly_white",
        hovermode="x unified",
        legend_title_text="Region",
        margin={"l": 40, "r": 20, "t": 70, "b": 40},
    )

    figure.update_xaxes(tickformat="%b %Y")

    figure.update_yaxes(
        tickprefix="$",
        tickformat=",.0f",
        separatethousands=True,
    )


def create_regional_revenue_chart(
    rows: Sequence[Mapping[str, Any]],
    analysis: RevenueAnalysis,
) -> go.Figure:
    """Create a monthly revenue chart with decline markers."""
    if not rows:
        raise ValueError("Cannot create a chart from an empty result.")

    records = _create_chart_records(rows)
    frame = _create_chart_frame(records)
    figure = _create_line_chart(frame)

    _add_decline_markers(figure, analysis)
    _format_chart(figure)

    return figure


def chart_to_spec(figure: go.Figure) -> dict[str, Any]:
    """Convert a Plotly figure into an API-friendly dictionary."""
    chart_specification = json.loads(figure.to_json())

    if not isinstance(chart_specification, dict):
        raise TypeError("Plotly did not produce an object specification.")

    return chart_specification
