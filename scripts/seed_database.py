import calendar
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values
from faker import Faker
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
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

CUSTOMER_COUNT = 1000
PRODUCT_COUNT = 100

REGION_NAMES = (
    "North",
    "South",
    "East",
    "West",
)

CUSTOMER_SEGMENTS = (
    "Consumer",
    "Corporate",
    "Small Business",
)

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

DISCOUNT_FACTORS = (
    "1.00",
    "0.95",
    "0.90",
)

DATABASE_MODELS = (
    Region,
    Customer,
    Product,
    Order,
    OrderItem,
    MonthlyTarget,
)


def iter_months(
    start: date,
    end: date,
) -> list[date]:
    months: list[date] = []

    current_month = date(
        start.year,
        start.month,
        1,
    )

    while current_month <= end:
        months.append(current_month)

        if current_month.month == 12:
            current_month = date(
                current_month.year + 1,
                1,
                1,
            )
        else:
            current_month = date(
                current_month.year,
                current_month.month + 1,
                1,
            )

    return months


def random_date_between(
    generator: random.Random,
    start: date,
    end: date,
) -> date:
    number_of_days = (end - start).days
    day_offset = generator.randint(
        0,
        number_of_days,
    )

    return start + timedelta(days=day_offset)


def create_regions() -> list[Region]:
    regions: list[Region] = []

    for region_id, region_name in enumerate(
        REGION_NAMES,
        start=1,
    ):
        region = Region(
            region_id=region_id,
            name=region_name,
        )
        regions.append(region)

    return regions


def create_customers(
    generator: random.Random,
    faker: Faker,
    regions: list[Region],
) -> tuple[
    list[Customer],
    dict[int, list[int]],
]:
    customers: list[Customer] = []

    customer_ids_by_region = {region.region_id: [] for region in regions}

    customer_start_date = date(2022, 1, 1)
    customer_end_date = date(2024, 7, 31)

    for customer_id in range(
        1,
        CUSTOMER_COUNT + 1,
    ):
        region_id = ((customer_id - 1) % len(regions)) + 1

        customer_name = faker.name()

        customer_segment = generator.choice(CUSTOMER_SEGMENTS)

        created_at = random_date_between(
            generator,
            customer_start_date,
            customer_end_date,
        )

        customer = Customer(
            customer_id=customer_id,
            region_id=region_id,
            name=customer_name,
            segment=customer_segment,
            created_at=created_at,
        )

        customers.append(customer)

        customer_ids_by_region[region_id].append(customer_id)

    return customers, customer_ids_by_region


def get_product_category(
    product_id: int,
) -> str:
    category_index = (product_id - 1) % len(PRODUCT_CATEGORIES)

    return PRODUCT_CATEGORIES[category_index]


def create_products(
    generator: random.Random,
) -> tuple[
    list[Product],
    dict[int, Decimal],
]:
    products: list[Product] = []
    product_prices: dict[int, Decimal] = {}

    for product_id in range(
        1,
        PRODUCT_COUNT + 1,
    ):
        category = get_product_category(product_id)

        minimum_price, maximum_price = PRICE_RANGES[category]

        random_price = generator.uniform(
            minimum_price,
            maximum_price,
        )

        unit_price = Decimal(f"{random_price:.2f}")

        product = Product(
            product_id=product_id,
            name=(f"{category} Product {product_id:03d}"),
            category=category,
            unit_price=unit_price,
        )

        products.append(product)
        product_prices[product_id] = unit_price

    return products, product_prices


def calculate_order_count(
    generator: random.Random,
    region_id: int,
    month: date,
) -> int:
    base_order_count = BASE_MONTHLY_ORDERS[region_id]

    order_count = base_order_count + generator.randint(-5, 5)

    decline_factor = INTENTIONAL_DECLINES.get((region_id, month))

    if decline_factor is not None:
        reduced_order_count = Decimal(order_count) * decline_factor

        order_count = max(
            1,
            int(reduced_order_count),
        )

    return order_count


def choose_order_status(
    generator: random.Random,
) -> str:
    if generator.random() < 0.96:
        return "completed"

    return "cancelled"


def calculate_sale_price(
    generator: random.Random,
    product_price: Decimal,
) -> Decimal:
    discount = Decimal(generator.choice(DISCOUNT_FACTORS))

    sale_price = product_price * discount

    return sale_price.quantize(Decimal("0.01"))


def create_order_items(
    generator: random.Random,
    order_id: int,
    first_order_item_id: int,
    product_prices: dict[int, Decimal],
) -> tuple[list[OrderItem], int]:
    order_items: list[OrderItem] = []

    number_of_items = generator.randint(
        1,
        4,
    )

    product_ids = generator.sample(
        range(1, PRODUCT_COUNT + 1),
        number_of_items,
    )

    order_item_id = first_order_item_id

    for product_id in product_ids:
        sale_price = calculate_sale_price(
            generator,
            product_prices[product_id],
        )

        quantity = generator.randint(1, 4)

        order_item = OrderItem(
            order_item_id=order_item_id,
            order_id=order_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=sale_price,
        )

        order_items.append(order_item)
        order_item_id += 1

    return order_items, order_item_id


def create_monthly_target(
    target_id: int,
    region_id: int,
    month: date,
) -> MonthlyTarget:
    base_order_count = BASE_MONTHLY_ORDERS[region_id]

    if month.month in (11, 12):
        seasonal_factor = Decimal("1.10")
    else:
        seasonal_factor = Decimal("1.00")

    revenue_target = (
        Decimal(base_order_count) * Decimal("550.00") * seasonal_factor
    ).quantize(Decimal("0.01"))

    return MonthlyTarget(
        target_id=target_id,
        region_id=region_id,
        month=month,
        revenue_target=revenue_target,
    )


def create_orders_and_targets(
    generator: random.Random,
    regions: list[Region],
    customer_ids_by_region: dict[
        int,
        list[int],
    ],
    product_prices: dict[int, Decimal],
) -> tuple[
    list[Order],
    list[OrderItem],
    list[MonthlyTarget],
]:
    orders: list[Order] = []
    order_items: list[OrderItem] = []
    monthly_targets: list[MonthlyTarget] = []

    order_id = 1
    order_item_id = 1
    target_id = 1

    months = iter_months(
        DATA_START,
        DATA_END,
    )

    for month in months:
        last_day = calendar.monthrange(
            month.year,
            month.month,
        )[1]

        for region in regions:
            region_id = region.region_id

            order_count = calculate_order_count(
                generator,
                region_id,
                month,
            )

            for _ in range(order_count):
                customer_id = generator.choice(customer_ids_by_region[region_id])

                # Keep this order unchanged. The fixed seed
                # depends on status being generated before day.
                order_status = choose_order_status(generator)

                order_day = generator.randint(
                    1,
                    last_day,
                )

                order = Order(
                    order_id=order_id,
                    customer_id=customer_id,
                    order_date=date(
                        month.year,
                        month.month,
                        order_day,
                    ),
                    status=order_status,
                )

                orders.append(order)

                (
                    new_order_items,
                    order_item_id,
                ) = create_order_items(
                    generator,
                    order_id,
                    order_item_id,
                    product_prices,
                )

                order_items.extend(new_order_items)

                order_id += 1

            monthly_target = create_monthly_target(
                target_id,
                region_id,
                month,
            )

            monthly_targets.append(monthly_target)

            target_id += 1

    return (
        orders,
        order_items,
        monthly_targets,
    )


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

    regions = create_regions()

    (
        customers,
        customer_ids_by_region,
    ) = create_customers(
        generator,
        faker,
        regions,
    )

    (
        products,
        product_prices,
    ) = create_products(generator)

    (
        orders,
        order_items,
        monthly_targets,
    ) = create_orders_and_targets(
        generator,
        regions,
        customer_ids_by_region,
        product_prices,
    )

    return (
        regions,
        customers,
        products,
        orders,
        order_items,
        monthly_targets,
    )


def get_admin_database_url() -> str:
    project_root = Path(__file__).resolve().parents[1]

    environment_file = project_root / ".env"

    environment = dotenv_values(environment_file)

    database_url = environment.get("DATABASE_ADMIN_URL")

    if not database_url:
        raise RuntimeError("DATABASE_ADMIN_URL is missing from the .env file.")

    return database_url


def recreate_tables(
    engine: Engine,
) -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def grant_reader_permissions(
    engine: Engine,
) -> None:
    table_permission_sql = "GRANT SELECT ON ALL TABLES IN SCHEMA public TO bi_reader"

    sequence_permission_sql = (
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bi_reader"
    )

    with engine.begin() as connection:
        connection.execute(text(table_permission_sql))

        connection.execute(text(sequence_permission_sql))


def save_seed_data(
    engine: Engine,
    regions: list[Region],
    customers: list[Customer],
    products: list[Product],
    orders: list[Order],
    order_items: list[OrderItem],
    monthly_targets: list[MonthlyTarget],
) -> None:
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


def print_table_counts(
    engine: Engine,
) -> None:
    print("Seed completed successfully:")

    with Session(engine) as session:
        for model in DATABASE_MODELS:
            row_count = session.scalar(select(func.count()).select_from(model))

            print(f"  {model.__tablename__}: {row_count}")


def main() -> None:
    database_url = get_admin_database_url()

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        print("Recreating the six synthetic retail tables...")

        recreate_tables(engine)
        grant_reader_permissions(engine)

        seed_data = build_seed_data()

        save_seed_data(
            engine,
            *seed_data,
        )

        print_table_counts(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
