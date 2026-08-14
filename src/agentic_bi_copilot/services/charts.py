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


def create_regional_revenue_chart(
    rows: Sequence[Mapping[str, Any]],
    analysis: RevenueAnalysis,
) -> go.Figure:
    if not rows:
        raise ValueError("Cannot create a chart from an empty result.")

    required_columns = {"month", "region", "revenue"}
    records: list[dict[str, Any]] = []

    for row_number, row in enumerate(rows, start=1):
        missing_columns = required_columns - row.keys()

        if missing_columns:
            missing_names = ", ".join(sorted(missing_columns))
            raise ValueError(
                f"Row {row_number} is missing columns: {missing_names}"
            )

        records.append(
            {
                "month": as_date(row["month"]),
                "region": str(row["region"]),
                "revenue": float(as_decimal(row["revenue"])),
            }
        )

    frame = pd.DataFrame.from_records(records)
    frame = frame.sort_values(
        ["region", "month"],
        kind="stable",
    )

    region_order = sorted(frame["region"].unique().tolist())

    figure = px.line(
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

    if analysis.unusual_declines:
        figure.add_trace(
            go.Scatter(
                x=[
                    finding.month
                    for finding in analysis.unusual_declines
                ],
                y=[
                    float(finding.revenue)
                    for finding in analysis.unusual_declines
                ],
                mode="markers",
                name="Unusual decline",
                marker={
                    "color": "#D62728",
                    "size": 12,
                    "symbol": "x",
                    "line": {"width": 2},
                },
                text=[
                    finding.region
                    for finding in analysis.unusual_declines
                ],
                customdata=[
                    float(finding.change_pct)
                    for finding in analysis.unusual_declines
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

    return figure


def chart_to_spec(figure: go.Figure) -> dict[str, Any]:
    chart_specification = json.loads(figure.to_json())

    if not isinstance(chart_specification, dict):
        raise TypeError("Plotly did not produce an object specification.")

    return chart_specification