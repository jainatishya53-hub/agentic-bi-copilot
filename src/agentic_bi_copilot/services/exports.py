import csv
import json
from io import StringIO
from typing import Any

from agentic_bi_copilot.services.run_history import (
    RunHistoryRecord,
)


class ExportDataError(ValueError):
    """Raised when stored result data cannot be exported."""


def build_json_export(
    record: RunHistoryRecord,
) -> str:
    """Create a readable JSON export for one completed run."""

    export_data = {
        "thread_id": record.thread_id,
        "question": record.question,
        "status": record.status,
        "source_thread_id": record.source_thread_id,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "result": record.result,
    }

    return json.dumps(
        export_data,
        indent=2,
        ensure_ascii=False,
    )


def build_csv_export(
    result: dict[str, Any],
) -> str:
    """Create a CSV export from query-result rows."""

    columns, rows = _get_query_data(result)

    output = StringIO(newline="")

    if not columns:
        return output.getvalue()

    writer = csv.DictWriter(
        output,
        fieldnames=columns,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()

    for row in rows:
        prepared_row = {
            column: _prepare_csv_value(row.get(column)) for column in columns
        }
        writer.writerow(prepared_row)

    return output.getvalue()


def _get_query_data(
    result: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Read and validate columns and rows from a stored result."""

    query_result = result.get("query_result")

    if not isinstance(query_result, dict):
        raise ExportDataError("The stored run does not contain a query result.")

    columns = query_result.get("columns")
    rows = query_result.get("rows")

    if not isinstance(columns, list) or not all(
        isinstance(column, str) for column in columns
    ):
        raise ExportDataError("The stored query columns are invalid.")

    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ExportDataError("The stored query rows are invalid.")

    return columns, rows


def _prepare_csv_value(value: Any) -> Any:
    """Convert complex values into readable CSV text."""

    if value is None:
        return ""

    if isinstance(value, dict | list):
        return json.dumps(
            value,
            ensure_ascii=False,
        )

    return value
