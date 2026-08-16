from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from agentic_bi_copilot.config import get_settings

ALLOWED_TABLES = frozenset(
    {
        "regions",
        "customers",
        "products",
        "orders",
        "order_items",
        "monthly_targets",
    }
)

ALLOWED_SCHEMAS = frozenset({"", "public"})

PROHIBITED_OPERATION_NAMES = frozenset(
    {
        "alter",
        "command",
        "commit",
        "copy",
        "create",
        "delete",
        "drop",
        "execute",
        "grant",
        "insert",
        "merge",
        "revoke",
        "rollback",
        "set",
        "transaction",
        "truncate",
        "truncatetable",
        "update",
        "use",
    }
)

PROHIBITED_FUNCTIONS = frozenset(
    {
        "dblink",
        "dblink_exec",
        "lo_export",
        "lo_import",
        "pg_ls_dir",
        "pg_read_binary_file",
        "pg_read_file",
        "pg_sleep",
        "pg_stat_file",
        "set_config",
    }
)


@dataclass(frozen=True, slots=True)
class SQLValidationResult:
    """Store the result of all SQL safety checks."""

    is_safe: bool
    normalized_sql: str | None
    referenced_tables: tuple[str, ...]
    checks: tuple[str, ...]
    errors: tuple[str, ...]


def invalid_result(
    *errors: str,
    referenced_tables: tuple[str, ...] = (),
) -> SQLValidationResult:
    """Create a failed SQL validation result."""
    return SQLValidationResult(
        is_safe=False,
        normalized_sql=None,
        referenced_tables=referenced_tables,
        checks=(),
        errors=errors,
    )


def _parse_query(sql: str) -> exp.Query | str:
    """Parse SQL and return either one query or an error message."""
    if not sql.strip():
        return "empty_query"

    try:
        statements = [
            statement
            for statement in parse(sql, read="postgres")
            if statement is not None
        ]
    except ParseError as error:
        return f"parse_error: {error}"

    if len(statements) != 1:
        return "multiple_statements"

    statement = statements[0]

    if not isinstance(statement, exp.Query):
        return "non_select_statement"

    return statement


def _find_prohibited_operation(
    statement: exp.Query,
) -> str | None:
    """Return the first prohibited SQL operation found."""
    for node in statement.walk():
        operation_name = type(node).__name__.lower()

        if operation_name in PROHIBITED_OPERATION_NAMES:
            return f"prohibited_operation: {operation_name}"

    return None


def _find_prohibited_function(
    statement: exp.Query,
) -> str | None:
    """Return the first prohibited SQL function found."""
    for function in statement.find_all(exp.Func):
        function_name = (function.name or function.sql_name()).lower()

        if function_name in PROHIBITED_FUNCTIONS:
            return f"prohibited_function: {function_name}"

    return None


def _get_cte_names(statement: exp.Query) -> set[str]:
    """Return the names of common table expressions in the query."""
    return {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}


def _get_referenced_tables(
    statement: exp.Query,
) -> tuple[tuple[str, ...], str | None]:
    """Collect allowed table names and report unauthorized references."""
    cte_names = _get_cte_names(statement)
    referenced_tables: set[str] = set()

    for table in statement.find_all(exp.Table):
        table_name = table.name.lower()
        schema_name = (table.db or "").lower()
        catalog_name = (table.catalog or "").lower()

        is_cte = not schema_name and not catalog_name and table_name in cte_names

        if is_cte:
            continue

        if catalog_name:
            return (), f"unauthorized_catalog: {catalog_name}"

        if schema_name not in ALLOWED_SCHEMAS:
            return (), f"unauthorized_schema: {schema_name}"

        if table_name not in ALLOWED_TABLES:
            return (), f"unauthorized_table: {table_name}"

        referenced_tables.add(table_name)

    return tuple(sorted(referenced_tables)), None


def _validate_limit(
    statement: exp.Query,
    max_result_rows: int,
) -> str | None:
    """Check that the query has a valid row limit."""
    limit_clause = statement.args.get("limit")

    if limit_clause is None:
        return "missing_limit"

    limit_expression = limit_clause.expression

    if not isinstance(limit_expression, exp.Literal) or limit_expression.is_string:
        return "invalid_limit"

    try:
        limit_value = int(limit_expression.this)
    except (TypeError, ValueError):
        return "invalid_limit"

    if limit_value <= 0:
        return "invalid_limit"

    if limit_value > max_result_rows:
        return f"limit_exceeds_{max_result_rows}"

    return None


def validate_sql(sql: str) -> SQLValidationResult:
    """Validate SQL before it is sent to the database."""
    settings = get_settings()

    parsed_result = _parse_query(sql)

    if isinstance(parsed_result, str):
        return invalid_result(parsed_result)

    statement = parsed_result

    operation_error = _find_prohibited_operation(statement)

    if operation_error is not None:
        return invalid_result(operation_error)

    function_error = _find_prohibited_function(statement)

    if function_error is not None:
        return invalid_result(function_error)

    referenced_tables, table_error = _get_referenced_tables(statement)

    if table_error is not None:
        return invalid_result(table_error)

    limit_error = _validate_limit(
        statement,
        settings.max_result_rows,
    )

    if limit_error is not None:
        return invalid_result(
            limit_error,
            referenced_tables=referenced_tables,
        )

    normalized_sql = statement.sql(
        dialect="postgres",
        pretty=True,
    )

    return SQLValidationResult(
        is_safe=True,
        normalized_sql=normalized_sql,
        referenced_tables=referenced_tables,
        checks=(
            "single_statement",
            "select_only",
            "no_prohibited_operations",
            "no_prohibited_functions",
            "allowed_schemas",
            "allowed_tables",
            "valid_row_limit",
        ),
        errors=(),
    )
