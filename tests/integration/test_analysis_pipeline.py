from datetime import date
from pathlib import Path

from agentic_bi_copilot.database.query_service import (
    execute_validated_query,
)
from agentic_bi_copilot.services.analysis import (
    analyze_regional_revenue,
)


def test_reference_query_produces_expected_analysis() -> None:
    query_path = (
        Path(__file__).parents[1]
        / "evaluation"
        / "regional_revenue_last_six_months.sql"
    )
    sql = query_path.read_text(encoding="utf-8")

    execution = execute_validated_query(sql)
    analysis = analyze_regional_revenue(
        execution.query_result.rows
    )

    assert analysis.top_region == "North"
    assert [
        (
            finding.region,
            finding.month,
            str(finding.change_pct),
        )
        for finding in analysis.unusual_declines
    ] == [
        ("West", date(2026, 7, 1), "-72.12"),
        ("South", date(2026, 5, 1), "-54.82"),
        ("West", date(2026, 3, 1), "-25.82"),
    ]