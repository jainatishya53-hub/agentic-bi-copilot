from sqlalchemy import text

from agentic_bi_copilot.database.connection import database_connection


def test_application_connects_as_readonly_user() -> None:
    query = text(
        """
        SELECT
            current_user AS user_name,
            current_database() AS database_name,
            current_setting('default_transaction_read_only') AS read_only,
            current_setting('statement_timeout') AS statement_timeout
        """
    )

    with database_connection() as connection:
        result = connection.execute(query).mappings().one()

    assert result["user_name"] == "bi_reader"
    assert result["database_name"] == "bi_copilot"
    assert result["read_only"] == "on"
    assert result["statement_timeout"] == "5s"