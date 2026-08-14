from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class RegionalRevenue:
    region: str
    revenue: Decimal


@dataclass(frozen=True, slots=True)
class DeclineFinding:
    region: str
    month: date
    revenue: Decimal
    previous_month_revenue: Decimal
    change_pct: Decimal


@dataclass(frozen=True, slots=True)
class RevenueAnalysis:
    total_revenue: Decimal
    top_region: str
    top_region_revenue: Decimal
    revenue_by_region: tuple[RegionalRevenue, ...]
    unusual_declines: tuple[DeclineFinding, ...]


def as_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


def analyze_regional_revenue(
    rows: Sequence[Mapping[str, Any]],
    decline_threshold: Decimal = Decimal(-20),
) -> RevenueAnalysis:
    if not rows:
        raise ValueError("Cannot analyze an empty result.")

    required_columns = {
        "month",
        "region",
        "revenue",
        "previous_month_revenue",
    }

    revenue_by_region: dict[str, Decimal] = {}
    declines: list[DeclineFinding] = []

    for row_number, row in enumerate(rows, start=1):
        missing_columns = required_columns - row.keys()

        if missing_columns:
            missing_names = ", ".join(sorted(missing_columns))
            raise ValueError(
                f"Row {row_number} is missing columns: {missing_names}"
            )

        region = str(row["region"])
        month = as_date(row["month"])
        revenue = as_decimal(row["revenue"])
        previous_value = row["previous_month_revenue"]

        revenue_by_region[region] = (
            revenue_by_region.get(region, Decimal(0)) + revenue
        )

        if previous_value is None:
            continue

        previous_revenue = as_decimal(previous_value)

        if previous_revenue == 0:
            continue

        change_pct = (
            ((revenue - previous_revenue) / previous_revenue)
            * Decimal(100)
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        if change_pct <= decline_threshold:
            declines.append(
                DeclineFinding(
                    region=region,
                    month=month,
                    revenue=revenue,
                    previous_month_revenue=previous_revenue,
                    change_pct=change_pct,
                )
            )

    ranked_regions = sorted(
        revenue_by_region.items(),
        key=lambda item: (-item[1], item[0]),
    )
    top_region, top_region_revenue = ranked_regions[0]

    regional_summaries = tuple(
        RegionalRevenue(region=region, revenue=revenue)
        for region, revenue in sorted(revenue_by_region.items())
    )

    sorted_declines = tuple(
        sorted(
            declines,
            key=lambda finding: (
                finding.change_pct,
                finding.region,
                finding.month,
            ),
        )
    )

    return RevenueAnalysis(
        total_revenue=sum(
            revenue_by_region.values(),
            start=Decimal(0),
        ).quantize(Decimal("0.01")),
        top_region=top_region,
        top_region_revenue=top_region_revenue.quantize(
            Decimal("0.01")
        ),
        revenue_by_region=regional_summaries,
        unusual_declines=sorted_declines,
    )