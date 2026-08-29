import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentic_bi_copilot.services.evaluation import (
    EvaluationCase,
    load_evaluation_cases,
)
from agentic_bi_copilot.services.evaluation_suite import (
    EvaluationSuiteResult,
    run_evaluation_suite,
)

DEFAULT_CASES_PATH = Path("tests/evaluation/cases.json")
DEFAULT_REPORT_PATH = Path("artifacts/evaluation_report.json")


def select_evaluation_cases(
    cases: Sequence[EvaluationCase],
    case_key: str | None,
) -> tuple[EvaluationCase, ...]:
    """Select one evaluation case or return every case."""

    if case_key is None:
        return tuple(cases)

    matching_cases = tuple(case for case in cases if case.key == case_key)

    if not matching_cases:
        raise ValueError(f"Unknown evaluation case: {case_key}")

    return matching_cases


def build_evaluation_report(
    suite_result: EvaluationSuiteResult,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Convert a suite result into a JSON-compatible report."""

    report_time = generated_at or datetime.now(UTC)

    return {
        "generated_at": report_time.isoformat(),
        "metrics": {
            "total_cases": suite_result.total_cases,
            "correct_cases": suite_result.correct_cases,
            "failed_cases": suite_result.failed_cases,
            "result_accuracy_pct": (suite_result.result_accuracy_pct),
            "chart_type_matches": (suite_result.chart_type_matches),
            "p95_processing_time_ms": (suite_result.p95_processing_time_ms),
        },
        "outcomes": [asdict(outcome) for outcome in suite_result.outcomes],
    }


def write_evaluation_report(
    report: dict[str, Any],
    output_path: Path,
) -> None:
    """Write an evaluation report to a JSON file."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """Create the evaluation command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate generated analytics results against trusted reference queries."
        )
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help="Path to the evaluation cases JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path for the generated JSON report.",
    )
    parser.add_argument(
        "--case-key",
        help=("Run one case instead of the full suite."),
    )

    return parser


def main() -> None:
    """Run the evaluation command."""

    parser = create_argument_parser()
    arguments = parser.parse_args()

    all_cases = load_evaluation_cases(arguments.cases)
    selected_cases = select_evaluation_cases(
        all_cases,
        arguments.case_key,
    )

    print(f"Running {len(selected_cases)} evaluation case(s)...")

    suite_result = run_evaluation_suite(
        selected_cases,
        arguments.cases,
    )
    report = build_evaluation_report(suite_result)
    write_evaluation_report(
        report,
        arguments.output,
    )

    if suite_result.p95_processing_time_ms is None:
        p95_display = "not available"
    else:
        p95_seconds = suite_result.p95_processing_time_ms / 1000
        p95_display = f"{p95_seconds:.2f} seconds"

    print(
        "Result accuracy: "
        f"{suite_result.result_accuracy_pct:.2f}% "
        f"({suite_result.correct_cases}/"
        f"{suite_result.total_cases})"
    )
    print(f"Failed cases: {suite_result.failed_cases}")
    print(f"p95 processing time: {p95_display}")
    print(f"Report written to: {arguments.output}")


if __name__ == "__main__":
    main()
