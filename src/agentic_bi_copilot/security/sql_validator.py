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
    is_safe: bool
    normalized_sql: str | None
    referenced_tables: tuple[str, ...]
    checks: tuple[str, ...]
    errors: tuple[str, ...]


def invalid_result(
    *errors: str,
    referenced_tables: tuple[str, ...] = (),
) -> SQLValidationResult:
    return SQLValidationResult(
        is_safe=False,
        normalized_sql=None,
        referenced_tables=referenced_tables,
        checks=(),
        errors=errors,
    )


def validate_sql(sql: str) -> SQLValidationResult:
    settings = get_settings()

    if not sql.strip():
        return invalid_result("empty_query")

    try:
        statements = [
            statement
            for statement in parse(sql, read="postgres")
            if statement is not None
        ]
    except ParseError as error:
        return invalid_result(f"parse_error: {error}")

    if len(statements) != 1:
        return invalid_result("multiple_statements")

    statement = statements[0]

    if not isinstance(statement, exp.Query):
        return invalid_result("non_select_statement")

    for node in statement.walk():
        operation_name = type(node).__name__.lower()

        if operation_name in PROHIBITED_OPERATION_NAMES:
            return invalid_result(
                f"prohibited_operation: {operation_name}"
            )

    for function in statement.find_all(exp.Func):
        function_name = (
            function.name or function.sql_name()
        ).lower()

        if function_name in PROHIBITED_FUNCTIONS:
            return invalid_result(
                f"prohibited_function: {function_name}"
            )

    cte_names = {
        cte.alias_or_name.lower()
        for cte in statement.find_all(exp.CTE)
    }

    referenced_tables: set[str] = set()

    for table in statement.find_all(exp.Table):
        table_name = table.name.lower()
        schema_name = (table.db or "").lower()
        catalog_name = (table.catalog or "").lower()

        if (
            not schema_name
            and not catalog_name
            and table_name in cte_names
        ):
            continue

        if catalog_name:
            return invalid_result(
                f"unauthorized_catalog: {catalog_name}"
            )

        if schema_name not in ALLOWED_SCHEMAS:
            return invalid_result(
                f"unauthorized_schema: {schema_name}"
            )

        if table_name not in ALLOWED_TABLES:
            return invalid_result(
                f"unauthorized_table: {table_name}"
            )

        referenced_tables.add(table_name)

    sorted_tables = tuple(sorted(referenced_tables))
    limit_clause = statement.args.get("limit")

    if limit_clause is None:
        return invalid_result(
            "missing_limit",
            referenced_tables=sorted_tables,
        )

    limit_expression = limit_clause.expression

    if (
        not isinstance(limit_expression, exp.Literal)
        or limit_expression.is_string
    ):
        return invalid_result(
            "invalid_limit",
            referenced_tables=sorted_tables,
        )

    try:
        limit_value = int(limit_expression.this)
    except (TypeError, ValueError):
        return invalid_result(
            "invalid_limit",
            referenced_tables=sorted_tables,
        )

    if limit_value <= 0:
        return invalid_result(
            "invalid_limit",
            referenced_tables=sorted_tables,
        )

    if limit_value > settings.max_result_rows:
        return invalid_result(
            f"limit_exceeds_{settings.max_result_rows}",
            referenced_tables=sorted_tables,
        )

    return SQLValidationResult(
        is_safe=True,
        normalized_sql=statement.sql(
            dialect="postgres",
            pretty=True,
        ),
        referenced_tables=sorted_tables,
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