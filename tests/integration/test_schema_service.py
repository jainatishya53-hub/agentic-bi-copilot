import pytest

from agentic_bi_copilot.database.schema_service import (
    build_schema_context,
    get_table_relationships,
    get_table_schema,
    list_tables,
)


def test_lists_only_allowed_tables() -> None:
    assert list_tables() == (
        "customers",
        "monthly_targets",
        "order_items",
        "orders",
        "products",
        "regions",
    )


def test_returns_product_schema() -> None:
    schema = get_table_schema("products")
    columns = {column.name: column for column in schema.columns}

    assert schema.name == "products"
    assert columns["product_id"].primary_key
    assert columns["name"].data_type == "VARCHAR(120)"
    assert columns["unit_price"].data_type == "NUMERIC(12, 2)"


def test_returns_expected_relationships() -> None:
    relationships = {
        (
            relationship.source_table,
            relationship.source_column,
            relationship.target_table,
            relationship.target_column,
        )
        for relationship in get_table_relationships()
    }

    assert relationships == {
        ("customers", "region_id", "regions", "region_id"),
        ("orders", "customer_id", "customers", "customer_id"),
        ("order_items", "order_id", "orders", "order_id"),
        ("order_items", "product_id", "products", "product_id"),
        (
            "monthly_targets",
            "region_id",
            "regions",
            "region_id",
        ),
    }


def test_builds_restricted_schema_context() -> None:
    context = build_schema_context(("orders", "customers", "regions"))

    assert "orders: Order headers." in context
    assert "customers.customer_id" in context
    assert "products:" not in context
    assert "Only orders with status = 'completed'" in context


def test_schema_context_defines_valid_order_statuses() -> None:
    context = build_schema_context(("orders",))

    assert "contains exactly 'completed' and 'cancelled'" in context
    assert "'canceled'" not in context


def test_rejects_unknown_table() -> None:
    with pytest.raises(
        ValueError,
        match="Unknown or disallowed tables",
    ):
        build_schema_context(("orders", "secret_table"))


def test_schema_context_defines_unusual_decline_threshold() -> None:
    context = build_schema_context(("orders", "order_items"))

    assert "below -25%" in context
