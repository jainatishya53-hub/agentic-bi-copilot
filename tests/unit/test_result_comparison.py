from datetime import date
from decimal import Decimal

from agentic_bi_copilot.services.evaluation import (
    compare_query_results,
)


def test_exact_results_match() -> None:
    comparison = compare_query_results(
        reference_columns=["month", "revenue"],
        reference_rows=[
            {
                "month": date(2026, 7, 1),
                "revenue": Decimal("125.50"),
            }
        ],
        candidate_columns=["month", "revenue"],
        candidate_rows=[
            {
                "month": date(2026, 7, 1),
                "revenue": Decimal("125.50"),
            }
        ],
    )

    assert comparison.is_correct is True
    assert comparison.columns_match is True
    assert comparison.row_count_match is True
    assert comparison.values_match is True


def test_row_order_can_be_ignored() -> None:
    comparison = compare_query_results(
        reference_columns=["region", "revenue"],
        reference_rows=[
            {"region": "North", "revenue": 200},
            {"region": "South", "revenue": 100},
        ],
        candidate_columns=["region", "revenue"],
        candidate_rows=[
            {"region": "South", "revenue": 100},
            {"region": "North", "revenue": 200},
        ],
        compare_row_order=False,
    )

    assert comparison.is_correct is True


def test_required_row_order_is_checked() -> None:
    comparison = compare_query_results(
        reference_columns=["region", "revenue"],
        reference_rows=[
            {"region": "North", "revenue": 200},
            {"region": "South", "revenue": 100},
        ],
        candidate_columns=["region", "revenue"],
        candidate_rows=[
            {"region": "South", "revenue": 100},
            {"region": "North", "revenue": 200},
        ],
        compare_row_order=True,
    )

    assert comparison.is_correct is False
    assert comparison.values_match is False


def test_numbers_are_compared_to_two_decimal_places() -> None:
    comparison = compare_query_results(
        reference_columns=["revenue"],
        reference_rows=[{"revenue": Decimal("100.005")}],
        candidate_columns=["revenue"],
        candidate_rows=[{"revenue": 100.01}],
    )

    assert comparison.is_correct is True


def test_different_columns_are_rejected() -> None:
    comparison = compare_query_results(
        reference_columns=["region", "revenue"],
        reference_rows=[{"region": "North", "revenue": 100}],
        candidate_columns=["region", "amount"],
        candidate_rows=[{"region": "North", "amount": 100}],
    )

    assert comparison.is_correct is False
    assert comparison.columns_match is False
    assert comparison.values_match is False


def test_different_row_counts_are_rejected() -> None:
    comparison = compare_query_results(
        reference_columns=["region"],
        reference_rows=[
            {"region": "North"},
            {"region": "South"},
        ],
        candidate_columns=["region"],
        candidate_rows=[{"region": "North"}],
    )

    assert comparison.is_correct is False
    assert comparison.row_count_match is False
    assert comparison.values_match is False


def test_different_values_are_rejected() -> None:
    comparison = compare_query_results(
        reference_columns=["region", "revenue"],
        reference_rows=[{"region": "North", "revenue": 100}],
        candidate_columns=["region", "revenue"],
        candidate_rows=[{"region": "North", "revenue": 90}],
    )

    assert comparison.is_correct is False
    assert comparison.values_match is False
