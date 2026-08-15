from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agentic_bi_copilot.agent.nodes import (
    AGENT_TABLES,
    DECLINE_THRESHOLD,
    analysis_node,
    chart_node,
    planning_node,
    query_execution_node,
    schema_discovery_node,
    sql_generation_node,
    sql_validation_node,
)
from agentic_bi_copilot.schemas import AnalysisPlan, SQLDraft


@dataclass
class FakeAnalysis:
    top_region: str
    top_region_revenue: Decimal


def test_schema_discovery_node_builds_restricted_context() -> None:
    with patch(
        "agentic_bi_copilot.agent.nodes.build_schema_context",
        return_value="restricted schema",
    ) as build_context:
        result = schema_discovery_node({})

    assert result["schema_context"] == "restricted schema"
    assert result["error"] is None
    build_context.assert_called_once_with(AGENT_TABLES)


def test_planning_node_stores_serializable_plan() -> None:
    expected_plan = AnalysisPlan(
        interpreted_question="Compare regional revenue.",
        required_tables=["orders", "order_items"],
        steps=["Calculate completed-order revenue."],
        assumptions=["Use the last six complete months."],
        needs_clarification=False,
        clarification_question=None,
    )

    state = {
        "question": "Compare regional revenue.",
        "schema_context": "restricted schema",
    }

    with patch(
        "agentic_bi_copilot.agent.nodes.create_analysis_plan",
        return_value=expected_plan,
    ) as create_plan:
        result = planning_node(state)

    assert result["plan"] == expected_plan.model_dump(mode="json")
    assert result["error"] is None
    create_plan.assert_called_once_with(
        question=state["question"],
        schema_context=state["schema_context"],
    )


def test_sql_generation_node_stores_draft() -> None:
    plan = AnalysisPlan(
        interpreted_question="Compare regional revenue.",
        required_tables=["regions", "customers", "orders", "order_items"],
        steps=["Calculate monthly regional revenue."],
        assumptions=["Completed orders count toward revenue."],
        needs_clarification=False,
        clarification_question=None,
    )

    expected_draft = SQLDraft(
        sql="SELECT name AS region FROM regions LIMIT 10",
        explanation="Lists regions.",
        referenced_tables=["regions"],
    )

    state = {
        "question": "Compare regional revenue.",
        "schema_context": "restricted schema",
        "plan": plan.model_dump(mode="json"),
    }

    with patch(
        "agentic_bi_copilot.agent.nodes.generate_sql",
        return_value=expected_draft,
    ) as create_sql:
        result = sql_generation_node(state)

    assert result["sql"] == expected_draft.sql
    assert result["sql_explanation"] == expected_draft.explanation
    assert result["referenced_tables"] == ["regions"]
    assert result["error"] is None

    create_sql.assert_called_once_with(
        question=state["question"],
        plan=plan,
        schema_context=state["schema_context"],
    )


def test_sql_validation_node_accepts_safe_query() -> None:
    result = sql_validation_node(
        {"sql": "SELECT name FROM regions ORDER BY name LIMIT 10"}
    )

    assert result["validation"]["is_safe"] is True
    assert result["validation"]["errors"] == []
    assert result["error"] is None


def test_sql_validation_node_rejects_write_query() -> None:
    result = sql_validation_node({"sql": "DELETE FROM regions"})

    assert result["validation"]["is_safe"] is False
    assert result["validation"]["errors"]
    assert result["error"] is not None


def test_query_execution_node_requires_approval() -> None:
    with (
        patch(
            "agentic_bi_copilot.agent.nodes.execute_validated_query"
        ) as execute_query,
        pytest.raises(
            PermissionError,
            match="explicit human approval",
        ),
    ):
        query_execution_node(
            {
                "approved": False,
                "sql": "SELECT name FROM regions LIMIT 10",
            }
        )

    execute_query.assert_not_called()


def test_query_execution_node_serializes_query_result() -> None:
    fake_result = SimpleNamespace(
        query_result=SimpleNamespace(
            columns=["month", "revenue"],
            rows=[
                {
                    "month": date(2026, 2, 1),
                    "revenue": Decimal("123.45"),
                }
            ],
            row_count=1,
            execution_time_ms=2.5,
        )
    )

    sql = "SELECT name FROM regions LIMIT 10"

    with patch(
        "agentic_bi_copilot.agent.nodes.execute_validated_query",
        return_value=fake_result,
    ) as execute_query:
        result = query_execution_node(
            {
                "approved": True,
                "sql": sql,
            }
        )

    execute_query.assert_called_once_with(sql)
    assert result["query_result"]["columns"] == ["month", "revenue"]
    assert result["query_result"]["rows"] == [
        {
            "month": "2026-02-01",
            "revenue": 123.45,
        }
    ]
    assert result["query_result"]["row_count"] == 1
    assert result["error"] is None


def test_analysis_node_creates_serializable_answer() -> None:
    rows = [{"region": "North", "revenue": 123.45}]
    fake_analysis = FakeAnalysis(
        top_region="North",
        top_region_revenue=Decimal("123.45"),
    )

    with (
        patch(
            "agentic_bi_copilot.agent.nodes.analyze_regional_revenue",
            return_value=fake_analysis,
        ) as analyze,
        patch(
            "agentic_bi_copilot.agent.nodes.create_business_answer",
            return_value="North generated the highest revenue.",
        ) as create_answer,
    ):
        result = analysis_node(
            {
                "query_result": {
                    "rows": rows,
                }
            }
        )

    analyze.assert_called_once_with(
        rows,
        decline_threshold=DECLINE_THRESHOLD,
    )
    create_answer.assert_called_once_with(fake_analysis)
    assert result["analysis"] == {
        "top_region": "North",
        "top_region_revenue": 123.45,
    }
    assert result["answer"] == "North generated the highest revenue."
    assert result["error"] is None


def test_chart_node_creates_serializable_specification() -> None:
    rows = [{"region": "North", "revenue": 123.45}]
    fake_analysis = object()
    fake_figure = object()
    fake_chart = {
        "data": [{"type": "scatter"}],
        "layout": {"title": "Regional revenue"},
    }

    with (
        patch(
            "agentic_bi_copilot.agent.nodes.analyze_regional_revenue",
            return_value=fake_analysis,
        ) as analyze,
        patch(
            "agentic_bi_copilot.agent.nodes.create_regional_revenue_chart",
            return_value=fake_figure,
        ) as create_chart,
        patch(
            "agentic_bi_copilot.agent.nodes.chart_to_spec",
            return_value=fake_chart,
        ) as create_spec,
    ):
        result = chart_node(
            {
                "query_result": {
                    "rows": rows,
                }
            }
        )

    analyze.assert_called_once_with(
        rows,
        decline_threshold=DECLINE_THRESHOLD,
    )
    create_chart.assert_called_once_with(rows, fake_analysis)
    create_spec.assert_called_once_with(fake_figure)
    assert result["chart"] == fake_chart
    assert result["error"] is None