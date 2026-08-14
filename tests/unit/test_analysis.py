from datetime import date
from decimal import Decimal

import pytest

from agentic_bi_copilot.services.analysis import (
    analyze_regional_revenue,
)


def test_calculates_regional_revenue_findings() -> None:
    rows = [
        {
            "month": date(2026, 7, 1),
            "region": "North",
            "revenue": Decimal("120.00"),
            "previous_month_revenue": Decimal("100.00"),
        },
        {
            "month": date(2026, 7, 1),
            "region": "South",
            "revenue": Decimal("80.00"),
            "previous_month_revenue": Decimal("100.00"),
        },
        {
            "month": date(2026, 7, 1),
            "region": "West",
            "revenue": Decimal("50.00"),
            "previous_month_revenue": Decimal("100.00"),
        },
    ]

    analysis = analyze_regional_revenue(rows)

    assert analysis.total_revenue == Decimal("250.00")
    assert analysis.top_region == "North"
    assert analysis.top_region_revenue == Decimal("120.00")
    assert [
        finding.region
        for finding in analysis.unusual_declines
    ] == ["West", "South"]
    assert analysis.unusual_declines[0].change_pct == Decimal(
        "-50.00"
    )


def test_rejects_empty_result() -> None:
    with pytest.raises(
        ValueError,
        match="Cannot analyze an empty result",
    ):
        analyze_regional_revenue([])


def test_rejects_missing_columns() -> None:
    with pytest.raises(
        ValueError,
        match="missing columns",
    ):
        analyze_regional_revenue(
            [
                {
                    "month": date(2026, 7, 1),
                    "region": "North",
                    "revenue": Decimal("100.00"),
                }
            ]
        )