"""
seed_large.py
-------------
Production-scale seed script for generating millions of rows.

Strategies used:
  1. Batch INSERT via executemany (1000 rows per query)
  2. LOAD DATA INFILE via CSV for largest tables
  3. FK constraint disabling during bulk load
  4. Auto-increment control to keep IDs predictable
  5. Progress reporting per batch

Usage:
  python seed_large.py                  # default: 1M orders
  python seed_large.py --orders 5000000 # 5M orders
"""

import MySQLdb
import csv
import os, sys
sys.path.append('/Users/abhi/myRepos/ecom_app')
import random
import argparse
import time
from datetime import datetime, timedelta
from itertools import islice
from app.config import settings

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BATCH_SIZE       = 10_000     # rows per INSERT batch
CSV_DIR          = "/tmp/ecom_seed"   # temp CSV files for LOAD DATA INFILE
NUM_ADDRESSES    = 50_000
NUM_CUSTOMERS    = 20_000
NUM_RESTAURANTS  = 500
NUM_ITEMS        = 5_000    # ~10 items per restaurant
NUM_PARTNERS     = 1_000
NUM_ORDERS       = 1_00_000 # change via --orders flag
EVENTS_PER_ORDER = 3         # average events per order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_conn():
    return MySQLdb.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        passwd=settings.db_password,
        db=settings.db_name,
        charset="utf8mb4",
        autocommit=False,
        local_infile=1
    )


def batched(iterable, n):
    """Yield successive n-sized chunks from iterable."""
    it = iter(iterable)
    while chunk := list(islice(it, n)):
        yield chunk


def progress(label, current, total, start_time):
    pct  = current / total * 100
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 else 0
    eta  = (total - current) / rate if rate > 0 else 0
    print(
        f"\r  {label}: {current:,}/{total:,} ({pct:.1f}%) "
        f"| {rate:,.0f} rows/s | ETA {eta:.0f}s",
        end="", flush=True,
    )


# ---------------------------------------------------------------------------
# Pre-flight: read actual check constraints from MySQL and validate
# before seeding millions of rows
# ---------------------------------------------------------------------------
def check_constraints(conn):
    """
    Reads all CHECK constraints on tables we seed and prints them
    so you can verify generators match before running millions of rows.
    """
    cur = conn.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT TABLE_NAME, CONSTRAINT_NAME, CHECK_CLAUSE
        FROM information_schema.CHECK_CONSTRAINTS cc
        JOIN information_schema.TABLE_CONSTRAINTS tc
          USING (CONSTRAINT_SCHEMA, CONSTRAINT_NAME)
        WHERE tc.TABLE_SCHEMA = DATABASE()
          AND tc.TABLE_NAME IN
              ('address','customers','restaurants','delivery_partners',
               'items','orders','order_items','order_events')
        ORDER BY TABLE_NAME, CONSTRAINT_NAME
    """)
    rows = cur.fetchall()
    if not rows:
        print("  No CHECK constraints found on target tables.")
        return
    print("  CHECK constraints found:")
    for r in rows:
        print(f"    [{r['TABLE_NAME']}] {r['CONSTRAINT_NAME']}: {r['CHECK_CLAUSE']}")
    print()


def rand_mobile():
    """
    Generates a valid Indian mobile number that satisfies the most
    common MySQL check constraints on mobile_number columns, e.g.:

        CONSTRAINT chk_mbl_num
            CHECK (mobile_number REGEXP '^[6-9][0-9]{9}$')

    Guarantees:
      Always exactly 10 digits
      Always starts with 6, 7, 8, or 9 (valid Indian prefixes)
      No spaces, country code, or + prefix
      Fits VARCHAR(15) without truncation
    """
    prefix = random.choice([6, 7, 8, 9])
    rest   = random.randint(100_000_000, 999_999_999)   # always 9 digits
    return f"{prefix}{rest}"                             # always 10 digits total


def rand_date(start_days_ago=365):
    return datetime.now() - timedelta(
        days=random.randint(0, start_days_ago),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


# ---------------------------------------------------------------------------
# Strategy 1: Batch INSERT via executemany
# Best for: 10K - 1M rows
# How: generate rows in Python, insert 1000 at a time
# ---------------------------------------------------------------------------

def batch_insert(conn, sql, row_generator, total, label):
    """
    Insert rows in batches of BATCH_SIZE using executemany.
    Much faster than one INSERT per row.

    On constraint violation:
      - Logs the offending batch number
      - Falls back to row-by-row insert for that batch so valid rows
        still go in and only the bad row is skipped with a clear error
    """
    cur     = conn.cursor()
    count   = 0
    skipped = 0
    start   = time.time()

    for batch_num, batch in enumerate(batched(row_generator, BATCH_SIZE), 1):
        try:
            cur.executemany(sql, batch)
            conn.commit()
            count += len(batch)
        except (MySQLdb.IntegrityError, MySQLdb.OperationalError) as e:
            conn.rollback()
            # Fallback: insert row by row to isolate the bad row
            for row in batch:
                try:
                    cur.execute(sql, row)
                    conn.commit()
                    count += 1
                except (MySQLdb.IntegrityError, MySQLdb.OperationalError) as row_err:
                    conn.rollback()
                    skipped += 1
                    print(f"\n  ⚠️  Skipped row in batch {batch_num}: {row_err.args[1]}")
                    print(f"     Offending row: {row}")
        progress(label, count, total, start)

    print(f"\n  ✅ {count:,} {label} inserted in {time.time()-start:.1f}s"
          + (f" | {skipped} skipped" if skipped else ""))
    return count


# ---------------------------------------------------------------------------
# Strategy 2: LOAD DATA INFILE
# Best for: 1M+ rows — fastest possible MySQL bulk load
# How: write CSV to disk, let MySQL read it directly (bypasses Python)
# ---------------------------------------------------------------------------

def write_csv_and_load(conn, table, columns, row_generator, total, label):
    """
    Write rows to a CSV file then use LOAD DATA INFILE.
    10-50x faster than executemany for very large datasets.
    """
    os.makedirs(CSV_DIR, exist_ok=True)
    csv_path = f"{CSV_DIR}/{table}.csv"
    start    = time.time()

    # Step 1: write CSV
    print(f"  Writing {label} CSV...")
    count = 0
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        for row in row_generator:
            writer.writerow(row)
            count += 1
            if count % 100_000 == 0:
                progress(f"Writing {label}", count, total, start)
    print(f"\n  CSV written: {csv_path} ({count:,} rows)")

    # Step 2: LOAD DATA INFILE — MySQL reads CSV directly
    col_list = ", ".join(columns)
    sql = f"""
        LOAD DATA LOCAL INFILE '{csv_path}'
        INTO TABLE {table}
        FIELDS TERMINATED BY ','
        OPTIONALLY ENCLOSED BY '"'
        LINES TERMINATED BY '\\n'
        ({col_list})
    """
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    print(f"  ✅ {count:,} {label} loaded via LOAD DATA INFILE in {time.time()-start:.1f}s")

    # Cleanup
    os.remove(csv_path)
    return count


# ---------------------------------------------------------------------------
# FK + index helpers
# Disabling FK checks and unique indexes during bulk load
# then re-enable after — speeds up inserts significantly
# ---------------------------------------------------------------------------

def disable_fk_and_indexes(conn):
    """
    Disable FK checks and autocommit for bulk loading.
    NEVER do this in production with live traffic.
    Safe only for initial seeding on empty tables.
    """
    cur = conn.cursor()
    cur.execute("COMMIT")  # Commit first to exit transaction
    cur.execute("SET foreign_key_checks = 0")
    cur.execute("SET unique_checks = 0")
    cur.execute("SET sql_log_bin = 0")          # skip binlog for speed
    print("  ⚡ FK checks and unique checks disabled for bulk load")


def enable_fk_and_indexes(conn):
    cur = conn.cursor()
    cur.execute("COMMIT")  #
    cur.execute("SET foreign_key_checks = 1")
    cur.execute("SET unique_checks = 1")
    cur.execute("SET sql_log_bin = 1")
    print("  ✅ FK checks and unique checks re-enabled")


# ---------------------------------------------------------------------------
# Row generators
# Pure Python generators — lazy, memory efficient
# Only one batch lives in memory at a time
# ---------------------------------------------------------------------------

CITIES    = ["Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune"]
LOCALITIES = ["Indiranagar", "Koramangala", "Whitefield", "HSR Layout",
              "Bandra", "Andheri", "Connaught Place", "Hitech City"]
STREETS   = ["MG Road", "Brigade Road", "Church Street", "Residency Road",
             "Link Road", "SV Road", "Ring Road", "Old Airport Road"]
STATUSES  = ["created", "confirmed", "preparing", "out_for_delivery",
             "delivered", "delivered", "delivered", "cancelled"]  # weighted toward delivered
EVENT_TRIGGERS = {
    "created":          "customer",
    "confirmed":        "restaurant",
    "preparing":        "restaurant",
    "out_for_delivery": "delivery_partner",
    "delivered":        "delivery_partner",
    "cancelled":        "customer",
}


def address_rows(n):
    types = ["home", "work", "restaurant", "other"]
    for i in range(n):
        yield (
            random.choice(types),
            str(random.randint(1, 999)),
            random.choice(STREETS),
            random.choice(LOCALITIES),
            random.choice(CITIES),
            f"{random.randint(400001, 600099)}",
            datetime.now(),
            datetime.now(),
        )


def customer_rows(n, address_id_start, address_id_end):
    statuses = ["active", "active", "active", "inactive", "blocked"]
    for i in range(n):
        created = rand_date()
        yield (
            random.randint(address_id_start, address_id_end),
            f"Customer {i+1}",
            rand_mobile(),
            f"customer{i+1}@example.com",
            random.choice(statuses),
            created,
            created,
        )


def restaurant_rows(n, address_id_start, address_id_end):
    cuisines = ["Biryani", "Pizza", "Burger", "Dosa", "Sushi",
                "Chinese", "Thai", "Mexican", "Continental", "Kebabs"]
    for i in range(n):
        created = rand_date()
        yield (
            random.randint(address_id_start, address_id_end),
            f"{random.choice(cuisines)} Place {i+1}",
            rand_mobile(),
            "active",
            created,
            created,
        )


def item_rows(n, restaurant_id_start, restaurant_id_end):
    food_names = ["Biryani", "Pizza", "Burger", "Dosa", "Pasta",
                  "Noodles", "Soup", "Salad", "Wrap", "Sandwich",
                  "Fried Rice", "Paneer Tikka", "Kebab", "Thali", "Paratha"]
    for i in range(n):
        created = rand_date()
        yield (
            random.randint(restaurant_id_start, restaurant_id_end),
            f"{random.choice(food_names)} {i+1}",
            round(random.uniform(49, 699), 2),
            1,   # is_available
            created,
            created,
        )


def delivery_partner_rows(n, address_id_start, address_id_end):
    statuses = ["available", "available", "on_trip", "offline"]
    for i in range(n):
        created = rand_date()
        yield (
            random.randint(address_id_start, address_id_end),
            f"Partner {i+1}",
            rand_mobile(),
            random.choice(statuses),
            created,
            created,
        )


def order_rows(
    n,
    customer_id_start, customer_id_end,
    restaurant_id_start, restaurant_id_end,
    partner_id_start, partner_id_end,
    address_id_start, address_id_end,
):
    for i in range(n):
        status   = random.choice(STATUSES)
        created  = rand_date()
        assigned = (
            random.randint(partner_id_start, partner_id_end)
            if status in ("out_for_delivery", "delivered") else None
        )
        yield (
            random.randint(customer_id_start,    customer_id_end),
            random.randint(restaurant_id_start,  restaurant_id_end),
            assigned,
            round(random.uniform(99, 1500), 2),  # total_amount
            status,
            random.randint(address_id_start, address_id_end),
            created,
            created,
        )


def order_item_rows(order_id_start, order_id_end,
                    item_id_start, item_id_end):
    """Generate 1-4 items per order."""
    for order_id in range(order_id_start, order_id_end + 1):
        for _ in range(random.randint(1, 4)):
            yield (
                order_id,
                random.randint(item_id_start, item_id_end),
                random.randint(1, 5),
                round(random.uniform(49, 699), 2),
                rand_date(),
            )


def order_event_rows(order_id_start, order_id_end, status_map):
    """
    Generate event log rows for each order.
    Each order gets the events matching its final status journey.
    Append-only — one row per status transition.
    """
    journey = {
        "created":          ["created"],
        "confirmed":        ["created", "confirmed"],
        "preparing":        ["created", "confirmed", "preparing"],
        "out_for_delivery": ["created", "confirmed", "preparing", "out_for_delivery"],
        "delivered":        ["created", "confirmed", "preparing", "out_for_delivery", "delivered"],
        "cancelled":        ["created", "cancelled"],
    }
    for order_id in range(order_id_start, order_id_end + 1):
        status  = status_map.get(order_id, "delivered")
        base_ts = rand_date()
        for j, evt in enumerate(journey.get(status, ["created"])):
            yield (
                order_id,
                evt,
                base_ts + timedelta(minutes=j * 10),
                EVENT_TRIGGERS.get(evt, "system"),
                base_ts + timedelta(minutes=j * 10),
            )


# ---------------------------------------------------------------------------
# Get auto-increment ranges after each bulk insert
# ---------------------------------------------------------------------------
def get_id_range(conn, table, pk_col="id"):
    """Return (min_id, max_id) of the given table."""
    cur = conn.cursor()
    cur.execute(f"SELECT MIN({pk_col}), MAX({pk_col}) FROM {table}")
    row = cur.fetchone()
    return (row[0] or 1, row[1] or 1)


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------
def seed(num_orders: int):
    print(f"\n🌱 Large-scale seed starting...")
    print(f"   Target: {num_orders:,} orders\n")

    conn = get_conn()

    # Pre-flight: print all check constraints so mismatches are caught early
    print("🔍 Reading CHECK constraints from MySQL...")
    check_constraints(conn)

    disable_fk_and_indexes(conn)

    try:
        # ---------------------------------------------------------------
        # 1. Addresses  — batch INSERT
        # ---------------------------------------------------------------
        print("📍 Seeding addresses...")
        batch_insert(
            conn,
            """INSERT INTO address
               (address_type, house_number, street, locality, city, pincode, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            address_rows(NUM_ADDRESSES),
            NUM_ADDRESSES, "addresses",
        )
        addr_min, addr_max = get_id_range(conn, "address")
        print(f"  Address IDs: {addr_min:,} → {addr_max:,}")

        # ---------------------------------------------------------------
        # 2. Customers  — batch INSERT
        # ---------------------------------------------------------------
        print("\n👤 Seeding customers...")
        batch_insert(
            conn,
            """INSERT INTO customers
               (address_id, name, mobile_number, email, status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            customer_rows(NUM_CUSTOMERS, addr_min, addr_max),
            NUM_CUSTOMERS, "customers",
        )
        cust_min, cust_max = get_id_range(conn, "customers")

        # ---------------------------------------------------------------
        # 3. Restaurants  — batch INSERT
        # ---------------------------------------------------------------
        print("\n🍽️  Seeding restaurants...")
        batch_insert(
            conn,
            """INSERT INTO restaurants
               (address_id, name, mobile_number, status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            restaurant_rows(NUM_RESTAURANTS, addr_min, addr_max),
            NUM_RESTAURANTS, "restaurants",
        )
        rest_min, rest_max = get_id_range(conn, "restaurants")

        # ---------------------------------------------------------------
        # 4. Items  — batch INSERT
        # ---------------------------------------------------------------
        print("\n🍕 Seeding items...")
        batch_insert(
            conn,
            """INSERT INTO items
               (restaurant_id, name, price, is_available, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            item_rows(NUM_ITEMS, rest_min, rest_max),
            NUM_ITEMS, "items",
        )
        item_min, item_max = get_id_range(conn, "items")

        # ---------------------------------------------------------------
        # 5. Delivery Partners  — batch INSERT
        # ---------------------------------------------------------------
        print("\n🛵 Seeding delivery partners...")
        batch_insert(
            conn,
            """INSERT INTO delivery_partners
               (address_id, name, mobile_number, status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            delivery_partner_rows(NUM_PARTNERS, addr_min, addr_max),
            NUM_PARTNERS, "delivery_partners",
        )
        part_min, part_max = get_id_range(conn, "delivery_partners")

        # ---------------------------------------------------------------
        # 6. Orders  — LOAD DATA INFILE (largest table)
        # ---------------------------------------------------------------
        print("\n📦 Seeding orders (LOAD DATA INFILE)...")
        write_csv_and_load(
            conn, "orders",
            ["customer_id", "restaurant_id", "delivery_partner_id",
             "total_amount", "status", "delivery_address_id",
             "created_at", "updated_at"],
            order_rows(
                num_orders,
                cust_min, cust_max,
                rest_min, rest_max,
                part_min, part_max,
                addr_min, addr_max,
            ),
            num_orders, "orders",
        )
        ord_min, ord_max = get_id_range(conn, "orders", pk_col="order_id")
        print(f"  Order IDs: {ord_min:,} → {ord_max:,}")

        # ---------------------------------------------------------------
        # 7. Build status map for event generation
        # Fetch order statuses so events match each order's journey
        # ---------------------------------------------------------------
        print("\n🗺️  Building order status map...")
        cur = conn.cursor()
        cur.execute("SELECT order_id, status FROM orders")
        status_map = {row[0]: row[1] for row in cur.fetchall()}
        print(f"  Loaded {len(status_map):,} order statuses")

        # ---------------------------------------------------------------
        # 8. Order Items  — LOAD DATA INFILE
        # ---------------------------------------------------------------
        print("\n🧾 Seeding order_items (LOAD DATA INFILE)...")
        estimated_items = num_orders * 2   # avg 2 items per order
        write_csv_and_load(
            conn, "order_items",
            ["order_id", "item_id", "quantity", "unit_price", "created_at"],
            order_item_rows(ord_min, ord_max, item_min, item_max),
            estimated_items, "order_items",
        )

        # ---------------------------------------------------------------
        # 9. Order Events  — LOAD DATA INFILE (biggest table of all)
        # Append-only — one row per status transition per order
        # ---------------------------------------------------------------
        print("\n📋 Seeding order_events (LOAD DATA INFILE)...")
        estimated_events = num_orders * EVENTS_PER_ORDER
        write_csv_and_load(
            conn, "order_events",
            ["order_id", "event_type", "event_timestamp",
             "triggered_by", "created_at"],
            order_event_rows(ord_min, ord_max, status_map),
            estimated_events, "order_events",
        )

        # ---------------------------------------------------------------
        # 10. ETL Watermark
        # ---------------------------------------------------------------
        print("\n⏱️  Seeding etl_watermark...")
        cur = conn.cursor()
        for table in ["order_events","customers","restaurants","items","orders"]:
            cur.execute(
                "INSERT IGNORE INTO etl_watermark (table_name, last_run) VALUES (%s, %s)",
                (table, "2000-01-01 00:00:00"),
            )
        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Seed failed: {e}")
        raise
    finally:
        enable_fk_and_indexes(conn)
        conn.close()

    print("\n✅ Large-scale seed complete!\n")
    print_summary(num_orders)


def print_summary(num_orders):
    print("=" * 50)
    print("📊 Estimated row counts:")
    print(f"  address           {NUM_ADDRESSES:>12,}")
    print(f"  customers         {NUM_CUSTOMERS:>12,}")
    print(f"  restaurants       {NUM_RESTAURANTS:>12,}")
    print(f"  items             {NUM_ITEMS:>12,}")
    print(f"  delivery_partners {NUM_PARTNERS:>12,}")
    print(f"  orders            {num_orders:>12,}")
    print(f"  order_items       {'~'+str(num_orders*2):>12}")
    print(f"  order_events      {'~'+str(num_orders*3):>12}")
    print("=" * 50)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Large-scale OLTP seed")
    parser.add_argument(
        "--orders", type=int, default=NUM_ORDERS,
        help=f"Number of orders to generate (default: {NUM_ORDERS:,})"
    )
    args = parser.parse_args()
    seed(args.orders)