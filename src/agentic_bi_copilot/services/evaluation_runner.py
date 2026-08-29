from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from agentic_bi_copilot.database.query_service import (
    execute_validated_query,
)
from agentic_bi_copilot.database.schema_service import (
    build_schema_context,
)
from agentic_bi_copilot.services.evaluation import (
    EvaluationCase,
    ResultComparison,
    compare_query_results,
    get_reference_sql_path,
)
from agentic_bi_copilot.services.llm import (
    create_analysis_plan,
    create_query_result_analysis,
    generate_sql,
)


class EvaluationCaseExecutionError(RuntimeError):
    """Raised when an evaluation case cannot be completed."""


@dataclass(frozen=True, slots=True)
class EvaluationRunResult:
    """Measured result for one evaluation case."""

    case_key: str
    generated_sql: str
    comparison: ResultComparison
    chart_type_match: bool
    processing_time_ms: float

    @property
    def is_correct(self) -> bool:
        """Return whether the generated query result is correct."""

        return self.comparison.is_correct


def read_reference_sql(
    case: EvaluationCase,
    cases_path: Path,
) -> str:
    """Read the trusted SQL query for an evaluation case."""

    reference_path = get_reference_sql_path(
        case,
        cases_path,
    )

    if not reference_path.is_file():
        raise EvaluationCaseExecutionError(
            f"Reference SQL does not exist: {reference_path}"
        )

    return reference_path.read_text(encoding="utf-8")


def run_evaluation_case(
    case: EvaluationCase,
    cases_path: Path,
) -> EvaluationRunResult:
    """Run one question and compare it with its reference result."""

    reference_sql = read_reference_sql(
        case,
        cases_path,
    )
    reference_result = execute_validated_query(reference_sql).query_result

    started_at = perf_counter()

    schema_context = build_schema_context(case.expected_tables)
    plan = create_analysis_plan(
        case.question,
        schema_context,
    )

    if plan.needs_clarification:
        clarification = (
            plan.clarification_question or "No clarification question was provided."
        )
        raise EvaluationCaseExecutionError(
            f"Evaluation question required clarification: {clarification}"
        )

    draft = generate_sql(
        case.question,
        plan,
        schema_context,
    )
    candidate_result = execute_validated_query(draft.sql).query_result

    result_analysis = create_query_result_analysis(
        case.question,
        candidate_result.columns,
        candidate_result.rows,
    )

    comparison = compare_query_results(
        reference_columns=reference_result.columns,
        reference_rows=reference_result.rows,
        candidate_columns=candidate_result.columns,
        candidate_rows=candidate_result.rows,
        compare_row_order=case.compare_row_order,
    )

    processing_time_ms = round(
        (perf_counter() - started_at) * 1000,
        2,
    )

    return EvaluationRunResult(
        case_key=case.key,
        generated_sql=draft.sql,
        comparison=comparison,
        chart_type_match=(result_analysis.chart.chart_type == case.expected_chart_type),
        processing_time_ms=processing_time_ms,
    )
