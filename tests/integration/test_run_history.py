from collections.abc import Iterator
from uuid import uuid4

import pytest

from agentic_bi_copilot.agent.persistence import close_checkpoint_pool
from agentic_bi_copilot.services.run_history import (
    RunNotFoundError,
    create_run,
    delete_run,
    get_run,
    list_runs,
    setup_run_history_table,
    update_run,
)


@pytest.fixture
def history_thread_ids() -> Iterator[list[str]]:
    """Track test records and remove them after each test."""

    setup_run_history_table()
    thread_ids: list[str] = []

    try:
        yield thread_ids
    finally:
        # Delete children before parents because retries reference earlier runs.
        for thread_id in reversed(thread_ids):
            delete_run(thread_id)

        close_checkpoint_pool()


def create_test_thread_id(
    history_thread_ids: list[str],
) -> str:
    """Create and remember a unique test thread ID."""

    thread_id = f"history-test-{uuid4()}"
    history_thread_ids.append(thread_id)
    return thread_id


def test_creates_and_reads_history_record(
    history_thread_ids: list[str],
) -> None:
    thread_id = create_test_thread_id(history_thread_ids)
    question = "Which region generated the highest revenue?"

    create_run(
        thread_id=thread_id,
        question=question,
        status="awaiting_approval",
    )

    record = get_run(thread_id)

    assert record is not None
    assert record.thread_id == thread_id
    assert record.question == question
    assert record.status == "awaiting_approval"
    assert record.source_thread_id is None
    assert record.result is None
    assert record.error is None


def test_updates_completed_run_with_json_result(
    history_thread_ids: list[str],
) -> None:
    thread_id = create_test_thread_id(history_thread_ids)

    create_run(
        thread_id=thread_id,
        question="Show the available sales regions.",
        status="awaiting_approval",
    )

    result = {
        "answer": "North is an available region.",
        "query_result": {
            "columns": ["name"],
            "rows": [{"name": "North"}],
            "row_count": 1,
        },
    }

    update_run(
        thread_id=thread_id,
        status="completed",
        result=result,
    )

    record = get_run(thread_id)

    assert record is not None
    assert record.status == "completed"
    assert record.result == result
    assert record.error is None
    assert record.updated_at >= record.created_at


def test_stores_retry_relationship_and_lists_runs(
    history_thread_ids: list[str],
) -> None:
    original_id = create_test_thread_id(history_thread_ids)
    retry_id = create_test_thread_id(history_thread_ids)
    question = "Compare monthly revenue across sales regions."

    create_run(
        thread_id=original_id,
        question=question,
        status="failed",
    )
    create_run(
        thread_id=retry_id,
        question=question,
        status="awaiting_approval",
        source_thread_id=original_id,
    )

    records = {
        record.thread_id: record
        for record in list_runs(limit=100)
        if record.thread_id in {original_id, retry_id}
    }

    assert set(records) == {original_id, retry_id}
    assert records[retry_id].source_thread_id == original_id
    assert records[original_id].source_thread_id is None


def test_rejects_invalid_history_limit() -> None:
    with pytest.raises(
        ValueError,
        match="between 1 and 100",
    ):
        list_runs(limit=0)

    with pytest.raises(
        ValueError,
        match="between 1 and 100",
    ):
        list_runs(limit=101)


def test_rejects_update_for_unknown_run(
    history_thread_ids: list[str],
) -> None:
    thread_id = create_test_thread_id(history_thread_ids)

    with pytest.raises(
        RunNotFoundError,
        match="was not found",
    ):
        update_run(
            thread_id=thread_id,
            status="failed",
            error="Test failure",
        )
