import json
from datetime import UTC, datetime

import pytest

from agentic_bi_copilot.services.exports import (
    ExportDataError,
    build_csv_export,
    build_json_export,
)
from agentic_bi_copilot.services.run_history import (
    RunHistoryRecord,
)


def create_completed_record() -> RunHistoryRecord:
    """Create a completed history record for export tests."""

    timestamp = datetime.now(UTC)

    return RunHistoryRecord(
        thread_id="export-run",
        question="Compare revenue across regions.",
        status="completed",
        source_thread_id=None,
        result={
            "answer": "North generated the highest revenue.",
            "query_result": {
                "columns": ["region", "revenue"],
                "rows": [
                    {
                        "region": "North",
                        "revenue": 1000.25,
                    },
                    {
                        "region": "South",
                        "revenue": 850.50,
                    },
                ],
                "row_count": 2,
            },
        },
        error=None,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_builds_json_export() -> None:
    record = create_completed_record()

    content = build_json_export(record)
    exported = json.loads(content)

    assert exported["thread_id"] == "export-run"
    assert exported["status"] == "completed"
    assert exported["result"]["answer"] == ("North generated the highest revenue.")
    assert exported["result"]["query_result"]["row_count"] == 2


def test_builds_csv_export() -> None:
    record = create_completed_record()

    assert record.result is not None

    content = build_csv_export(record.result)

    assert content.splitlines() == [
        "region,revenue",
        "North,1000.25",
        "South,850.5",
    ]


def test_rejects_result_without_query_data() -> None:
    with pytest.raises(
        ExportDataError,
        match="does not contain a query result",
    ):
        build_csv_export(
            {
                "answer": "No query result is available.",
            }
        )
