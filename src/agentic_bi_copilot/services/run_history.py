from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from agentic_bi_copilot.agent.persistence import get_checkpoint_pool

RunStatus = Literal[
    "awaiting_approval",
    "completed",
    "rejected",
    "failed",
]


class RunNotFoundError(LookupError):
    """Raised when an analysis run cannot be found."""


@dataclass(frozen=True, slots=True)
class RunHistoryRecord:
    thread_id: str
    question: str
    status: RunStatus
    source_thread_id: str | None
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    approval: dict[str, Any] | None = None


def setup_run_history_table() -> None:
    """Create the analysis history table when it does not exist."""

    pool = get_checkpoint_pool()

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_state.analysis_runs (
                    thread_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_thread_id TEXT NULL,
                    approval JSONB NULL,
                    result JSONB NULL,
                    error TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                    CONSTRAINT ck_analysis_runs_question_length
                        CHECK (
                            CHAR_LENGTH(question) >= 10
                            AND CHAR_LENGTH(question) <= 500
                        ),

                    CONSTRAINT ck_analysis_runs_status
                        CHECK (
                            status IN (
                                'awaiting_approval',
                                'completed',
                                'rejected',
                                'failed'
                            )
                        ),

                    CONSTRAINT fk_analysis_runs_source
                        FOREIGN KEY (source_thread_id)
                        REFERENCES agent_state.analysis_runs(thread_id)
                        ON DELETE SET NULL
                )
                """
            )

            # This safely updates databases created before approval storage.
            cursor.execute(
                """
                ALTER TABLE agent_state.analysis_runs
                ADD COLUMN IF NOT EXISTS approval JSONB NULL
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_analysis_runs_updated_at
                ON agent_state.analysis_runs(updated_at DESC)
                """
            )

        connection.commit()


def create_run(
    thread_id: str,
    question: str,
    status: RunStatus = "awaiting_approval",
    source_thread_id: str | None = None,
) -> RunHistoryRecord:
    """Create a history record for a new analysis run."""

    pool = get_checkpoint_pool()

    with pool.connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO agent_state.analysis_runs (
                    thread_id,
                    question,
                    status,
                    source_thread_id
                )
                VALUES (%s, %s, %s, %s)
                RETURNING
                    thread_id,
                    question,
                    status,
                    source_thread_id,
                    approval,
                    result,
                    error,
                    created_at,
                    updated_at
                """,
                (
                    thread_id,
                    question,
                    status,
                    source_thread_id,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    if row is None:
        raise RuntimeError("The analysis run could not be created.")

    return _build_run_record(row)


def update_run(
    thread_id: str,
    status: RunStatus,
    *,
    approval: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> RunHistoryRecord:
    """Update the status and stored information for an analysis run."""

    stored_approval = Jsonb(approval) if approval is not None else None
    stored_result = Jsonb(result) if result is not None else None
    pool = get_checkpoint_pool()

    with pool.connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                UPDATE agent_state.analysis_runs
                SET
                    status = %s,
                    approval = COALESCE(%s, approval),
                    result = %s,
                    error = %s,
                    updated_at = NOW()
                WHERE thread_id = %s
                RETURNING
                    thread_id,
                    question,
                    status,
                    source_thread_id,
                    approval,
                    result,
                    error,
                    created_at,
                    updated_at
                """,
                (
                    status,
                    stored_approval,
                    stored_result,
                    error,
                    thread_id,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    if row is None:
        raise RunNotFoundError(f"Analysis run '{thread_id}' was not found.")

    return _build_run_record(row)


def get_run(thread_id: str) -> RunHistoryRecord | None:
    """Return one analysis run or None when it does not exist."""

    pool = get_checkpoint_pool()

    with (
        pool.connection() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        cursor.execute(
            """
            SELECT
                thread_id,
                question,
                status,
                source_thread_id,
                approval,
                result,
                error,
                created_at,
                updated_at
            FROM agent_state.analysis_runs
            WHERE thread_id = %s
            """,
            (thread_id,),
        )

        row = cursor.fetchone()

    if row is None:
        return None

    return _build_run_record(row)


def list_runs(limit: int = 20) -> list[RunHistoryRecord]:
    """Return recent analysis runs, with the newest run first."""

    if limit < 1 or limit > 100:
        raise ValueError("History limit must be between 1 and 100.")

    pool = get_checkpoint_pool()

    with (
        pool.connection() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        cursor.execute(
            """
            SELECT
                thread_id,
                question,
                status,
                source_thread_id,
                approval,
                result,
                error,
                created_at,
                updated_at
            FROM agent_state.analysis_runs
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )

        rows = cursor.fetchall()

    return [_build_run_record(row) for row in rows]


def delete_run(thread_id: str) -> bool:
    """Delete an analysis history record."""

    pool = get_checkpoint_pool()

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM agent_state.analysis_runs
                WHERE thread_id = %s
                """,
                (thread_id,),
            )

            deleted = cursor.rowcount > 0

        connection.commit()

    return deleted


def _build_run_record(
    row: Mapping[str, Any],
) -> RunHistoryRecord:
    """Convert a database row into a run history record."""

    approval = row.get("approval")
    result = row.get("result")

    if approval is not None and not isinstance(approval, dict):
        raise TypeError("Stored approval must be a JSON object.")

    if result is not None and not isinstance(result, dict):
        raise TypeError("Stored result must be a JSON object.")

    return RunHistoryRecord(
        thread_id=str(row["thread_id"]),
        question=str(row["question"]),
        status=row["status"],
        source_thread_id=row.get("source_thread_id"),
        approval=approval,
        result=result,
        error=row.get("error"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
