from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.engine.reflection import Inspector

from agentic_bi_copilot.database.connection import get_engine
from agentic_bi_copilot.security.sql_validator import ALLOWED_TABLES

TABLE_DESCRIPTIONS = {
    "regions": "Geographic sales regions.",
    "customers": "Customers assigned to a region and business segment.",
    "products": "Products with category and current list price.",
    "orders": "Order headers. Only completed orders count as revenue.",
    "order_items": (
        "Products sold in each order, including quantity and sale-time price."
    ),
    "monthly_targets": "Monthly revenue target for each region.",
}


BUSINESS_RULES = (
    "Revenue equals SUM(order_items.quantity * order_items.unit_price).",
    "Only orders with status = 'completed' count toward revenue.",
    (
        "The orders.status column contains exactly 'completed' and "
        "'cancelled'. Use 'cancelled' with two l characters."
    ),
    "The dataset ends on 2026-07-31.",
    "The last six complete months are 2026-02-01 through 2026-07-31.",
    "An unusual decline is a month-over-month revenue change below -25%.",
)


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    """Describe one database column."""

    name: str
    data_type: str
    nullable: bool
    primary_key: bool


@dataclass(frozen=True, slots=True)
class TableSchema:
    """Describe one allowed database table."""

    name: str
    description: str
    columns: tuple[ColumnSchema, ...]


@dataclass(frozen=True, slots=True)
class TableRelationship:
    """Describe a foreign-key relationship between two tables."""

    source_table: str
    source_column: str
    target_table: str
    target_column: str


def get_inspector() -> Inspector:
    """Create a SQLAlchemy database inspector."""

    return inspect(get_engine())


def list_tables() -> tuple[str, ...]:
    """Return the allowed tables that exist in the database."""

    inspector = get_inspector()
    database_tables = set(inspector.get_table_names(schema="public"))

    allowed_database_tables = database_tables & ALLOWED_TABLES

    return tuple(sorted(allowed_database_tables))


def _normalize_table_name(table_name: str) -> str:
    """Clean a table name before checking it."""

    return table_name.strip().lower()


def _get_primary_key_columns(
    inspector: Inspector,
    table_name: str,
) -> set[str]:
    """Return the primary-key columns for a table."""

    primary_key = inspector.get_pk_constraint(
        table_name,
        schema="public",
    )

    return set(primary_key.get("constrained_columns") or ())


def _get_columns(
    inspector: Inspector,
    table_name: str,
    primary_key_columns: set[str],
) -> tuple[ColumnSchema, ...]:
    """Build the column descriptions for a table."""

    database_columns = inspector.get_columns(
        table_name,
        schema="public",
    )

    return tuple(
        ColumnSchema(
            name=column["name"],
            data_type=str(column["type"]),
            nullable=bool(column["nullable"]),
            primary_key=column["name"] in primary_key_columns,
        )
        for column in database_columns
    )


def get_table_schema(table_name: str) -> TableSchema:
    """Return the schema of one allowed table."""

    normalized_name = _normalize_table_name(table_name)

    if normalized_name not in ALLOWED_TABLES:
        raise ValueError(f"Table is not allowed: {table_name}")

    if normalized_name not in list_tables():
        raise ValueError(f"Table does not exist: {table_name}")

    inspector = get_inspector()
    primary_key_columns = _get_primary_key_columns(
        inspector,
        normalized_name,
    )
    columns = _get_columns(
        inspector,
        normalized_name,
        primary_key_columns,
    )

    return TableSchema(
        name=normalized_name,
        description=TABLE_DESCRIPTIONS[normalized_name],
        columns=columns,
    )


def get_table_relationships() -> tuple[TableRelationship, ...]:
    """Return relationships between allowed tables."""

    inspector = get_inspector()
    relationships: list[TableRelationship] = []

    for source_table in list_tables():
        foreign_keys = inspector.get_foreign_keys(
            source_table,
            schema="public",
        )

        for foreign_key in foreign_keys:
            target_table = foreign_key["referred_table"]

            if target_table not in ALLOWED_TABLES:
                continue

            source_columns = foreign_key["constrained_columns"]
            target_columns = foreign_key["referred_columns"]

            for source_column, target_column in zip(
                source_columns,
                target_columns,
            ):
                relationship = TableRelationship(
                    source_table=source_table,
                    source_column=source_column,
                    target_table=target_table,
                    target_column=target_column,
                )
                relationships.append(relationship)

    return tuple(
        sorted(
            relationships,
            key=lambda relationship: (
                relationship.source_table,
                relationship.source_column,
            ),
        )
    )


def _select_tables(
    selected_tables: tuple[str, ...] | None,
    available_tables: set[str],
) -> set[str]:
    """Choose and validate the tables used in the schema context."""

    if selected_tables is None:
        return available_tables

    requested_tables = {_normalize_table_name(table) for table in selected_tables}

    unknown_tables = requested_tables - available_tables

    if unknown_tables:
        names = ", ".join(sorted(unknown_tables))
        raise ValueError(f"Unknown or disallowed tables: {names}")

    return requested_tables


def _format_column(column: ColumnSchema) -> str:
    """Format one column for the text schema context."""

    attributes: list[str] = []

    if column.primary_key:
        attributes.append("primary key")

    if not column.nullable:
        attributes.append("not null")

    suffix = ""

    if attributes:
        suffix = f" ({', '.join(attributes)})"

    return f"- {column.name}: {column.data_type}{suffix}"


def _add_table_details(
    lines: list[str],
    requested_tables: set[str],
) -> None:
    """Add table and column details to the context."""

    for table_name in sorted(requested_tables):
        table_schema = get_table_schema(table_name)

        lines.append(f"{table_schema.name}: {table_schema.description}")

        for column in table_schema.columns:
            lines.append(_format_column(column))


def _add_relationships(
    lines: list[str],
    requested_tables: set[str],
) -> None:
    """Add relationships between the selected tables."""

    for relationship in get_table_relationships():
        source_is_selected = relationship.source_table in requested_tables
        target_is_selected = relationship.target_table in requested_tables

        if source_is_selected and target_is_selected:
            lines.append(
                f"- {relationship.source_table}."
                f"{relationship.source_column} -> "
                f"{relationship.target_table}."
                f"{relationship.target_column}"
            )


def build_schema_context(
    selected_tables: tuple[str, ...] | None = None,
) -> str:
    """Build the database information given to the language model."""

    available_tables = set(list_tables())
    requested_tables = _select_tables(
        selected_tables,
        available_tables,
    )

    lines = [
        "Database dialect: PostgreSQL",
        "",
        "Business rules:",
    ]

    lines.extend(f"- {rule}" for rule in BUSINESS_RULES)
    lines.extend(("", "Tables:"))

    _add_table_details(lines, requested_tables)

    lines.extend(("", "Relationships:"))
    _add_relationships(lines, requested_tables)

    return "\n".join(lines)
