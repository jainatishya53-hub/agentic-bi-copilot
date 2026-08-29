from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agentic_bi_copilot.database.query_service import QueryResult
from agentic_bi_copilot.schemas import (
    AnalysisPlan,
    ChartRecommendation,
    QueryResultAnalysis,
    SQLDraft,
)
from agentic_bi_copilot.services import evaluation_runner
from agentic_bi_copilot.services.evaluation import EvaluationCase
from agentic_bi_copilot.services.evaluation_runner import (
    EvaluationCaseExecutionError,
    run_evaluation_case,
)


def create_case() -> EvaluationCase:
    return EvaluationCase(
        key="top_products",
        question="Which products generated the most revenue?",
        expected_tables=(
            "orders",
            "order_items",
            "products",
        ),
        expected_columns=(
            "product_name",
            "total_revenue",
        ),
        expected_chart_type="bar",
        reference_sql_file="top_products.sql",
        compare_row_order=True,
    )


def create_query_result(
    revenue: float,
) -> QueryResult:
    return QueryResult(
        columns=[
            "product_name",
            "total_revenue",
        ],
        rows=[
            {
                "product_name": "Product A",
                "total_revenue": revenue,
            }
        ],
        row_count=1,
        execution_time_ms=1.0,
    )


def test_runs_evaluation_case_and_compares_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = create_case()
    cases_path = tmp_path / "cases.json"
    reference_path = tmp_path / "top_products.sql"
    reference_path.write_text(
        "SELECT reference LIMIT 500;\n",
        encoding="utf-8",
    )

    requested_tables: list[tuple[str, ...]] = []

    def fake_build_schema_context(
        selected_tables: tuple[str, ...] | None = None,
    ) -> str:
        if selected_tables is not None:
            requested_tables.append(selected_tables)

        return "test schema"

    def fake_create_analysis_plan(
        question: str,
        schema_context: str,
    ) -> AnalysisPlan:
        assert question == case.question
        assert schema_context == "test schema"

        return AnalysisPlan(
            interpreted_question=question,
            required_tables=list(case.expected_tables),
            steps=["Calculate product revenue."],
            assumptions=[],
            needs_clarification=False,
            clarification_question=None,
        )

    def fake_generate_sql(
        question: str,
        plan: AnalysisPlan,
        schema_context: str,
    ) -> SQLDraft:
        assert question == case.question
        assert plan.needs_clarification is False
        assert schema_context == "test schema"

        return SQLDraft(
            sql="SELECT candidate LIMIT 500;",
            explanation="Test SQL",
            referenced_tables=list(case.expected_tables),
        )

    def fake_execute_validated_query(
        sql: str,
    ) -> SimpleNamespace:
        if "reference" in sql:
            query_result = create_query_result(100.0)
        else:
            query_result = create_query_result(100.0)

        return SimpleNamespace(query_result=query_result)

    def fake_create_query_result_analysis(
        question: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> QueryResultAnalysis:
        assert question == case.question
        assert columns == [
            "product_name",
            "total_revenue",
        ]
        assert len(rows) == 1

        return QueryResultAnalysis(
            analysis_type="ranking",
            answer="Product A generated the most revenue.",
            key_findings=["Product A ranked first."],
            follow_up_questions=["Which products grew the fastest?"],
            chart=ChartRecommendation(
                chart_type="bar",
                title="Top Products",
                x_column="product_name",
                y_column="total_revenue",
                color_column=None,
            ),
        )

    monkeypatch.setattr(
        evaluation_runner,
        "build_schema_context",
        fake_build_schema_context,
    )
    monkeypatch.setattr(
        evaluation_runner,
        "create_analysis_plan",
        fake_create_analysis_plan,
    )
    monkeypatch.setattr(
        evaluation_runner,
        "generate_sql",
        fake_generate_sql,
    )
    monkeypatch.setattr(
        evaluation_runner,
        "execute_validated_query",
        fake_execute_validated_query,
    )
    monkeypatch.setattr(
        evaluation_runner,
        "create_query_result_analysis",
        fake_create_query_result_analysis,
    )

    result = run_evaluation_case(
        case,
        cases_path,
    )

    assert requested_tables == [case.expected_tables]
    assert result.case_key == case.key
    assert result.generated_sql == ("SELECT candidate LIMIT 500;")
    assert result.is_correct is True
    assert result.chart_type_match is True
    assert result.processing_time_ms >= 0


def test_rejects_case_that_requires_clarification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = create_case()
    cases_path = tmp_path / "cases.json"
    reference_path = tmp_path / "top_products.sql"
    reference_path.write_text(
        "SELECT reference LIMIT 500;\n",
        encoding="utf-8",
    )

    def fake_create_analysis_plan(
        question: str,
        schema_context: str,
    ) -> AnalysisPlan:
        return AnalysisPlan(
            interpreted_question=question,
            required_tables=[],
            steps=[],
            assumptions=[],
            needs_clarification=True,
            clarification_question=("Which date range should be used?"),
        )

    monkeypatch.setattr(
        evaluation_runner,
        "execute_validated_query",
        lambda sql: SimpleNamespace(query_result=create_query_result(100.0)),
    )
    monkeypatch.setattr(
        evaluation_runner,
        "build_schema_context",
        lambda selected_tables: "test schema",
    )
    monkeypatch.setattr(
        evaluation_runner,
        "create_analysis_plan",
        fake_create_analysis_plan,
    )

    with pytest.raises(
        EvaluationCaseExecutionError,
        match="required clarification",
    ):
        run_evaluation_case(
            case,
            cases_path,
        )
