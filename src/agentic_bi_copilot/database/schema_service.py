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
    "The dataset ends on 2026-07-31.",
    "The last six complete months are 2026-02-01 through 2026-07-31.",
    "An unusual decline is a month-over-month revenue change below -25%.",
)


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool
    primary_key: bool


@dataclass(frozen=True, slots=True)
class TableSchema:
    name: str
    description: str
    columns: tuple[ColumnSchema, ...]


@dataclass(frozen=True, slots=True)
class TableRelationship:
    source_table: str
    source_column: str
    target_table: str
    target_column: str


def get_inspector() -> Inspector:
    return inspect(get_engine())


def list_tables() -> tuple[str, ...]:
    inspector = get_inspector()
    database_tables = set(
        inspector.get_table_names(schema="public")
    )

    return tuple(sorted(database_tables & ALLOWED_TABLES))


def get_table_schema(table_name: str) -> TableSchema:
    normalized_name = table_name.strip().lower()

    if normalized_name not in ALLOWED_TABLES:
        raise ValueError(f"Table is not allowed: {table_name}")

    if normalized_name not in list_tables():
        raise ValueError(f"Table does not exist: {table_name}")

    inspector = get_inspector()
    primary_key = inspector.get_pk_constraint(
        normalized_name,
        schema="public",
    )
    primary_key_columns = set(
        primary_key.get("constrained_columns") or ()
    )

    columns = tuple(
        ColumnSchema(
            name=column["name"],
            data_type=str(column["type"]),
            nullable=bool(column["nullable"]),
            primary_key=column["name"] in primary_key_columns,
        )
        for column in inspector.get_columns(
            normalized_name,
            schema="public",
        )
    )

    return TableSchema(
        name=normalized_name,
        description=TABLE_DESCRIPTIONS[normalized_name],
        columns=columns,
    )


def get_table_relationships() -> tuple[TableRelationship, ...]:
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
                relationships.append(
                    TableRelationship(
                        source_table=source_table,
                        source_column=source_column,
                        target_table=target_table,
                        target_column=target_column,
                    )
                )

    return tuple(
        sorted(
            relationships,
            key=lambda relationship: (
                relationship.source_table,
                relationship.source_column,
            ),
        )
    )


def build_schema_context(
    selected_tables: tuple[str, ...] | None = None,
) -> str:
    available_tables = set(list_tables())

    if selected_tables is None:
        requested_tables = available_tables
    else:
        requested_tables = {
            table.strip().lower()
            for table in selected_tables
        }

    unknown_tables = requested_tables - available_tables

    if unknown_tables:
        names = ", ".join(sorted(unknown_tables))
        raise ValueError(f"Unknown or disallowed tables: {names}")

    lines = [
        "Database dialect: PostgreSQL",
        "",
        "Business rules:",
    ]

    lines.extend(f"- {rule}" for rule in BUSINESS_RULES)
    lines.extend(("", "Tables:"))

    for table_name in sorted(requested_tables):
        table_schema = get_table_schema(table_name)
        lines.append(
            f"{table_schema.name}: {table_schema.description}"
        )

        for column in table_schema.columns:
            attributes: list[str] = []

            if column.primary_key:
                attributes.append("primary key")
            if not column.nullable:
                attributes.append("not null")

            suffix = (
                f" ({', '.join(attributes)})"
                if attributes
                else ""
            )

            lines.append(
                f"- {column.name}: {column.data_type}{suffix}"
            )

    lines.extend(("", "Relationships:"))

    for relationship in get_table_relationships():
        if (
            relationship.source_table in requested_tables
            and relationship.target_table in requested_tables
        ):
            lines.append(
                f"- {relationship.source_table}."
                f"{relationship.source_column} -> "
                f"{relationship.target_table}."
                f"{relationship.target_column}"
            )

    return "\n".join(lines)