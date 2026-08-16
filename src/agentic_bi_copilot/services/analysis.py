from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

REQUIRED_COLUMNS = {
    "month",
    "region",
    "revenue",
    "previous_month_revenue",
}

DECIMAL_ZERO = Decimal(0)
PERCENTAGE_MULTIPLIER = Decimal(100)
TWO_DECIMAL_PLACES = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class RegionalRevenue:
    """Store the total revenue for one region."""

    region: str
    revenue: Decimal


@dataclass(frozen=True, slots=True)
class DeclineFinding:
    """Store information about an unusual revenue decline."""

    region: str
    month: date
    revenue: Decimal
    previous_month_revenue: Decimal
    change_pct: Decimal


@dataclass(frozen=True, slots=True)
class RevenueAnalysis:
    """Store the completed regional revenue analysis."""

    total_revenue: Decimal
    top_region: str
    top_region_revenue: Decimal
    revenue_by_region: tuple[RegionalRevenue, ...]
    unusual_declines: tuple[DeclineFinding, ...]


def as_decimal(value: Any) -> Decimal:
    """Convert a value to Decimal without losing precision."""
    return Decimal(str(value))


def as_date(value: Any) -> date:
    """Convert a supported value to a date."""
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


def _validate_row(
    row: Mapping[str, Any],
    row_number: int,
) -> None:
    """Check that a query row contains all required columns."""
    missing_columns = REQUIRED_COLUMNS - row.keys()

    if missing_columns:
        missing_names = ", ".join(sorted(missing_columns))
        raise ValueError(f"Row {row_number} is missing columns: {missing_names}")


def _calculate_change_percentage(
    revenue: Decimal,
    previous_revenue: Decimal,
) -> Decimal:
    """Calculate the percentage change between two months."""
    change = (revenue - previous_revenue) / previous_revenue * PERCENTAGE_MULTIPLIER

    return change.quantize(
        TWO_DECIMAL_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _create_regional_summaries(
    revenue_by_region: dict[str, Decimal],
) -> tuple[RegionalRevenue, ...]:
    """Create summaries ordered alphabetically by region."""
    return tuple(
        RegionalRevenue(
            region=region,
            revenue=revenue,
        )
        for region, revenue in sorted(revenue_by_region.items())
    )


def _sort_declines(
    declines: list[DeclineFinding],
) -> tuple[DeclineFinding, ...]:
    """Sort declines from the largest drop to the smallest."""
    return tuple(
        sorted(
            declines,
            key=lambda finding: (
                finding.change_pct,
                finding.region,
                finding.month,
            ),
        )
    )


def _get_top_region(
    revenue_by_region: dict[str, Decimal],
) -> tuple[str, Decimal]:
    """Return the region with the highest total revenue."""
    ranked_regions = sorted(
        revenue_by_region.items(),
        key=lambda item: (-item[1], item[0]),
    )

    return ranked_regions[0]


def analyze_regional_revenue(
    rows: Sequence[Mapping[str, Any]],
    decline_threshold: Decimal = Decimal(-20),
) -> RevenueAnalysis:
    """Analyze revenue totals and unusual monthly declines."""
    if not rows:
        raise ValueError("Cannot analyze an empty result.")

    revenue_by_region: dict[str, Decimal] = {}
    declines: list[DeclineFinding] = []

    for row_number, row in enumerate(rows, start=1):
        _validate_row(row, row_number)

        region = str(row["region"])
        month = as_date(row["month"])
        revenue = as_decimal(row["revenue"])
        previous_value = row["previous_month_revenue"]

        current_total = revenue_by_region.get(
            region,
            DECIMAL_ZERO,
        )
        revenue_by_region[region] = current_total + revenue

        # A percentage change cannot be calculated without a
        # non-zero previous-month value.
        if previous_value is None:
            continue

        previous_revenue = as_decimal(previous_value)

        if previous_revenue == DECIMAL_ZERO:
            continue

        change_pct = _calculate_change_percentage(
            revenue,
            previous_revenue,
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

    top_region, top_region_revenue = _get_top_region(revenue_by_region)

    total_revenue = sum(
        revenue_by_region.values(),
        start=DECIMAL_ZERO,
    ).quantize(TWO_DECIMAL_PLACES)

    return RevenueAnalysis(
        total_revenue=total_revenue,
        top_region=top_region,
        top_region_revenue=top_region_revenue.quantize(TWO_DECIMAL_PLACES),
        revenue_by_region=_create_regional_summaries(revenue_by_region),
        unusual_declines=_sort_declines(declines),
    )
