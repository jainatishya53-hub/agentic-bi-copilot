from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""


class Region(Base):
    """Store the available sales regions."""

    __tablename__ = "regions"

    region_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )


class Customer(Base):
    """Store customer details and their assigned regions."""

    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.region_id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    segment: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    created_at: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "segment IN ('Consumer', 'Corporate', 'Small Business')",
            name="ck_customers_segment",
        ),
    )


class Product(Base):
    """Store products and their standard prices."""

    __tablename__ = "products"

    product_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "unit_price > 0",
            name="ck_products_positive_price",
        ),
    )


class Order(Base):
    """Store order-level information."""

    __tablename__ = "orders"

    order_id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.customer_id"),
        nullable=False,
        index=True,
    )
    order_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'cancelled')",
            name="ck_orders_status",
        ),
    )


class OrderItem(Base):
    """Store the products and quantities included in each order."""

    __tablename__ = "order_items"

    order_item_id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.product_id"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_order_items_positive_quantity",
        ),
        CheckConstraint(
            "unit_price > 0",
            name="ck_order_items_positive_price",
        ),
    )


class MonthlyTarget(Base):
    """Store the monthly revenue target for each region."""

    __tablename__ = "monthly_targets"

    target_id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.region_id"),
        nullable=False,
        index=True,
    )
    month: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    revenue_target: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "region_id",
            "month",
            name="uq_monthly_targets_region_month",
        ),
        CheckConstraint(
            "revenue_target >= 0",
            name="ck_monthly_targets_nonnegative",
        ),
    )
