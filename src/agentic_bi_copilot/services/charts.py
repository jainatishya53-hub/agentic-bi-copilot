import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from agentic_bi_copilot.schemas import ChartRecommendation
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
    """Check that a regional row contains the required columns."""

    missing_columns = REQUIRED_CHART_COLUMNS - row.keys()

    if missing_columns:
        missing_names = ", ".join(sorted(missing_columns))
        raise ValueError(f"Row {row_number} is missing columns: {missing_names}")


def _create_chart_records(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Convert regional revenue rows into chart records."""

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
    """Create and sort the regional revenue data frame."""

    frame = pd.DataFrame.from_records(records)

    return frame.sort_values(
        ["region", "month"],
        kind="stable",
    )


def _create_line_chart(frame: pd.DataFrame) -> go.Figure:
    """Create the original regional revenue line chart."""

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


def _format_regional_chart(figure: go.Figure) -> None:
    """Apply formatting to the original regional chart."""

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
    _format_regional_chart(figure)

    return figure


def _normalize_generic_value(value: Any) -> Any:
    """Convert database values into values Plotly can display."""

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return value


def _create_generic_frame(
    rows: Sequence[Mapping[str, Any]],
) -> pd.DataFrame:
    """Create a data frame from a general query result."""

    records = [
        {str(column): _normalize_generic_value(value) for column, value in row.items()}
        for row in rows
    ]

    return pd.DataFrame.from_records(records)


def _chart_columns_exist(
    frame: pd.DataFrame,
    recommendation: ChartRecommendation,
) -> bool:
    """Check that a chart uses columns contained in the result."""

    if recommendation.chart_type == "table":
        return True

    if recommendation.x_column is None or recommendation.y_column is None:
        return False

    available_columns = set(frame.columns)
    selected_columns = (
        recommendation.x_column,
        recommendation.y_column,
        recommendation.color_column,
    )

    return all(
        column is None or column in available_columns for column in selected_columns
    )


def _create_empty_figure(title: str) -> go.Figure:
    """Create a simple figure for an empty query result."""

    figure = go.Figure()

    figure.add_annotation(
        text="No matching data was returned.",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 16},
    )

    figure.update_layout(
        title=title,
        template="plotly_white",
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 40, "r": 20, "t": 70, "b": 40},
    )

    return figure


def _create_table_figure(
    frame: pd.DataFrame,
    title: str,
) -> go.Figure:
    """Display a query result as a Plotly table."""

    columns = list(frame.columns)

    figure = go.Figure(
        data=[
            go.Table(
                header={
                    "values": columns,
                    "align": "left",
                    "fill_color": "#E8EEF7",
                    "font": {
                        "color": "#172033",
                        "size": 12,
                    },
                },
                cells={
                    "values": [frame[column].tolist() for column in columns],
                    "align": "left",
                    "fill_color": "#FFFFFF",
                    "font": {
                        "color": "#263449",
                        "size": 11,
                    },
                },
            )
        ]
    )

    figure.update_layout(
        title=title,
        template="plotly_white",
        margin={"l": 20, "r": 20, "t": 70, "b": 20},
    )

    return figure


def _create_recommended_chart(
    frame: pd.DataFrame,
    recommendation: ChartRecommendation,
) -> go.Figure:
    """Create the line or bar chart selected by the analysis."""

    chart_arguments = {
        "data_frame": frame,
        "x": recommendation.x_column,
        "y": recommendation.y_column,
        "color": recommendation.color_column,
        "title": recommendation.title,
    }

    if recommendation.chart_type == "line":
        return px.line(
            **chart_arguments,
            markers=True,
        )

    figure = px.bar(**chart_arguments)

    if recommendation.chart_type == "grouped_bar":
        figure.update_layout(barmode="group")

    return figure


def _format_generic_chart(figure: go.Figure) -> None:
    """Apply shared formatting to a general chart."""

    figure.update_layout(
        template="plotly_white",
        margin={"l": 40, "r": 20, "t": 70, "b": 40},
        legend_title_text="",
    )


def create_query_result_chart(
    rows: Sequence[Mapping[str, Any]],
    recommendation: ChartRecommendation,
) -> go.Figure:
    """Create a chart for a general query result."""

    if not rows:
        return _create_empty_figure(recommendation.title)

    frame = _create_generic_frame(rows)

    if recommendation.chart_type == "table":
        return _create_table_figure(
            frame,
            recommendation.title,
        )

    # Invalid recommendations safely fall back to a table.
    if not _chart_columns_exist(
        frame,
        recommendation,
    ):
        return _create_table_figure(
            frame,
            recommendation.title,
        )

    figure = _create_recommended_chart(
        frame,
        recommendation,
    )
    _format_generic_chart(figure)

    return figure


def chart_to_spec(figure: go.Figure) -> dict[str, Any]:
    """Convert a Plotly figure into an API-friendly dictionary."""

    chart_specification = json.loads(figure.to_json())

    if not isinstance(chart_specification, dict):
        raise TypeError("Plotly did not produce an object specification.")

    return chart_specification
