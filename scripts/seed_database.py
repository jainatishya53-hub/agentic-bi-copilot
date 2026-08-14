import calendar
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values
from faker import Faker
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from agentic_bi_copilot.database.models import (
    Base,
    Customer,
    MonthlyTarget,
    Order,
    OrderItem,
    Product,
    Region,
)

SEED = 20260815
DATA_START = date(2024, 8, 1)
DATA_END = date(2026, 7, 31)

REGION_NAMES = ("North", "South", "East", "West")
CUSTOMER_SEGMENTS = ("Consumer", "Corporate", "Small Business")
PRODUCT_CATEGORIES = (
    "Electronics",
    "Furniture",
    "Office Supplies",
    "Apparel",
    "Home",
)

BASE_MONTHLY_ORDERS = {
    1: 65,
    2: 55,
    3: 50,
    4: 45,
}

PRICE_RANGES = {
    "Electronics": (40, 300),
    "Furniture": (50, 500),
    "Office Supplies": (5, 80),
    "Apparel": (10, 150),
    "Home": (10, 200),
}

INTENTIONAL_DECLINES = {
    (2, date(2026, 5, 1)): Decimal("0.40"),
    (4, date(2026, 7, 1)): Decimal("0.45"),
}


def iter_months(start: date, end: date) -> list[date]:
    months: list[date] = []
    current = date(start.year, start.month, 1)

    while current <= end:
        months.append(current)

        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return months


def random_date_between(
    generator: random.Random,
    start: date,
    end: date,
) -> date:
    day_offset = generator.randint(0, (end - start).days)
    return start + timedelta(days=day_offset)


def build_seed_data() -> tuple[
    list[Region],
    list[Customer],
    list[Product],
    list[Order],
    list[OrderItem],
    list[MonthlyTarget],
]:
    generator = random.Random(SEED)
    faker = Faker("en_US")
    faker.seed_instance(SEED)

    regions = [
        Region(region_id=index, name=name)
        for index, name in enumerate(REGION_NAMES, start=1)
    ]

    customers: list[Customer] = []
    customer_ids_by_region: dict[int, list[int]] = {
        region.region_id: [] for region in regions
    }

    for customer_id in range(1, 1001):
        region_id = ((customer_id - 1) % len(regions)) + 1

        customers.append(
            Customer(
                customer_id=customer_id,
                region_id=region_id,
                name=faker.name(),
                segment=generator.choice(CUSTOMER_SEGMENTS),
                created_at=random_date_between(
                    generator,
                    date(2022, 1, 1),
                    date(2024, 7, 31),
                ),
            )
        )
        customer_ids_by_region[region_id].append(customer_id)

    products: list[Product] = []
    product_prices: dict[int, Decimal] = {}

    for product_id in range(1, 101):
        category = PRODUCT_CATEGORIES[
            (product_id - 1) % len(PRODUCT_CATEGORIES)
        ]
        minimum_price, maximum_price = PRICE_RANGES[category]
        unit_price = Decimal(
            f"{generator.uniform(minimum_price, maximum_price):.2f}"
        )

        products.append(
            Product(
                product_id=product_id,
                name=f"{category} Product {product_id:03d}",
                category=category,
                unit_price=unit_price,
            )
        )
        product_prices[product_id] = unit_price

    orders: list[Order] = []
    order_items: list[OrderItem] = []
    monthly_targets: list[MonthlyTarget] = []

    order_id = 1
    order_item_id = 1
    target_id = 1

    for month in iter_months(DATA_START, DATA_END):
        for region in regions:
            base_order_count = BASE_MONTHLY_ORDERS[region.region_id]
            order_count = base_order_count + generator.randint(-5, 5)

            decline_factor = INTENTIONAL_DECLINES.get(
                (region.region_id, month)
            )
            if decline_factor is not None:
                order_count = max(
                    1,
                    int(Decimal(order_count) * decline_factor),
                )

            last_day = calendar.monthrange(month.year, month.month)[1]

            for _ in range(order_count):
                customer_id = generator.choice(
                    customer_ids_by_region[region.region_id]
                )
                status = (
                    "completed"
                    if generator.random() < 0.96
                    else "cancelled"
                )

                orders.append(
                    Order(
                        order_id=order_id,
                        customer_id=customer_id,
                        order_date=date(
                            month.year,
                            month.month,
                            generator.randint(1, last_day),
                        ),
                        status=status,
                    )
                )

                number_of_items = generator.randint(1, 4)
                product_ids = generator.sample(
                    range(1, 101),
                    number_of_items,
                )

                for product_id in product_ids:
                    discount = Decimal(
                        generator.choice(("1.00", "0.95", "0.90"))
                    )
                    sale_price = (
                        product_prices[product_id] * discount
                    ).quantize(Decimal("0.01"))

                    order_items.append(
                        OrderItem(
                            order_item_id=order_item_id,
                            order_id=order_id,
                            product_id=product_id,
                            quantity=generator.randint(1, 4),
                            unit_price=sale_price,
                        )
                    )
                    order_item_id += 1

                order_id += 1

            seasonal_factor = (
                Decimal("1.10")
                if month.month in (11, 12)
                else Decimal("1.00")
            )
            revenue_target = (
                Decimal(base_order_count)
                * Decimal("550.00")
                * seasonal_factor
            ).quantize(Decimal("0.01"))

            monthly_targets.append(
                MonthlyTarget(
                    target_id=target_id,
                    region_id=region.region_id,
                    month=month,
                    revenue_target=revenue_target,
                )
            )
            target_id += 1

    return (
        regions,
        customers,
        products,
        orders,
        order_items,
        monthly_targets,
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    environment = dotenv_values(project_root / ".env")
    admin_database_url = environment.get("DATABASE_ADMIN_URL")

    if not admin_database_url:
        raise RuntimeError(
            "DATABASE_ADMIN_URL is missing from the .env file."
        )

    engine = create_engine(admin_database_url, pool_pre_ping=True)

    print("Recreating the six synthetic retail tables...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "GRANT SELECT ON ALL TABLES IN SCHEMA public TO bi_reader"
            )
        )
        connection.execute(
            text(
                "GRANT USAGE, SELECT ON ALL SEQUENCES "
                "IN SCHEMA public TO bi_reader"
            )
        )

    (
    regions,
    customers,
    products,
    orders,
    order_items,
    monthly_targets,
   ) = build_seed_data()

    with Session(engine) as session:
        session.add_all(regions)
        session.add_all(products)
        session.flush()

        session.add_all(customers)
        session.add_all(monthly_targets)
        session.flush()

        session.add_all(orders)
        session.flush()

        session.add_all(order_items)
        session.commit()

    models = (
        Region,
        Customer,
        Product,
        Order,
        OrderItem,
        MonthlyTarget,
    )

    print("Seed completed successfully:")
    with Session(engine) as session:
        for model in models:
            row_count = session.scalar(
                select(func.count()).select_from(model)
            )
            print(f"  {model.__tablename__}: {row_count}")

    engine.dispose()


if __name__ == "__main__":
    main()