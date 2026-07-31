"""Seeds mcp_server.db with a deterministic 50k-row e-commerce dataset.

Run once — skips if the `orders` table already has rows. Idempotent by design
so `docker compose up` never re-seeds an existing volume.
"""

import random

from faker import Faker

from db import CATEGORIES, ORDER_STATUSES, REGIONS, get_connection, init_schema, is_seeded

SEED = 42
CUSTOMER_COUNT = 5_000
PRODUCT_COUNT = 200
ORDER_COUNT = 50_000
YEARS_OF_HISTORY = 3

STATUS_WEIGHTS = [0.55, 0.30, 0.10, 0.05]  # completed, shipped, pending, cancelled


def seed_customers(fake: Faker, conn) -> None:
    rows = []
    for customer_id in range(1, CUSTOMER_COUNT + 1):
        signup_date = fake.date_between(start_date=f"-{YEARS_OF_HISTORY}y", end_date="today")
        rows.append(
            (
                customer_id,
                fake.name(),
                fake.unique.email(),
                fake.city(),
                fake.country(),
                signup_date.isoformat(),
            )
        )
    conn.executemany(
        "INSERT INTO customers (customer_id, name, email, city, country, signup_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )


def seed_products(fake: Faker, conn) -> list[tuple[int, str, float]]:
    rows = []
    for product_id in range(1, PRODUCT_COUNT + 1):
        category = random.choice(CATEGORIES)
        cost_price = round(random.uniform(5, 500), 2)
        rows.append((product_id, fake.catch_phrase(), category, cost_price))
    conn.executemany(
        "INSERT INTO products (product_id, name, category, cost_price) VALUES (?, ?, ?, ?)",
        rows,
    )
    return [(pid, cost) for pid, _, _, cost in rows]


def seed_orders_and_items(fake: Faker, conn, products: list[tuple[int, float]]) -> None:
    order_rows = []
    item_rows = []
    item_id = 1

    for order_id in range(1, ORDER_COUNT + 1):
        customer_id = random.randint(1, CUSTOMER_COUNT)
        order_date = fake.date_time_between(start_date=f"-{YEARS_OF_HISTORY}y", end_date="now")
        status = random.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        region = random.choice(REGIONS)

        n_items = random.randint(1, 5)
        chosen = random.sample(products, k=n_items)
        total_amount = 0.0
        for product_id, cost_price in chosen:
            quantity = random.randint(1, 5)
            unit_price = round(cost_price * random.uniform(1.2, 2.5), 2)
            item_rows.append((item_id, order_id, product_id, quantity, unit_price))
            total_amount += quantity * unit_price
            item_id += 1

        order_rows.append(
            (order_id, customer_id, order_date.isoformat(sep=" "), status, round(total_amount, 2), region)
        )

    conn.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, status, total_amount, region) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        order_rows,
    )
    conn.executemany(
        "INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price) "
        "VALUES (?, ?, ?, ?, ?)",
        item_rows,
    )


def main() -> None:
    random.seed(SEED)
    fake = Faker()
    Faker.seed(SEED)

    conn = get_connection()
    init_schema(conn)

    if is_seeded(conn):
        print("mcp_server.db already seeded — skipping.")
        conn.close()
        return

    print(f"Seeding {CUSTOMER_COUNT} customers, {PRODUCT_COUNT} products, {ORDER_COUNT} orders...")
    seed_customers(fake, conn)
    products = seed_products(fake, conn)
    seed_orders_and_items(fake, conn, products)
    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
