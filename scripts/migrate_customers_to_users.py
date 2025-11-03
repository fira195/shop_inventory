"""Migration helper: convert existing `customer` table rows into `user` rows
and map all foreign keys which referenced `customer.id` to `user.id`.

USAGE (dry-run):
    python scripts/migrate_customers_to_users.py --dry-run

USAGE (apply):
    python scripts/migrate_customers_to_users.py --apply

Caveats / assumptions:
- Your project must have a working `.venv` with the project's requirements installed.
- This script inspects the `customer` table for at least `id` and `phone` columns.
  If a `hashed_password` column exists it will be reused; otherwise a random
  password is generated and hashed for the new user (printed to the console).
- The script will create a new nullable `user_id` column on target tables
  (sale, repair, customerbalance) and populate it. After you verify the data,
  you can drop the old `customer` table via the script using --drop-customer.
- This is destructive: BACKUP your database before running with --apply.

The script is intentionally conservative: it performs a dry-run by default
and will only modify data when --apply is passed.
"""

import argparse
import secrets
import string
import sys
from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Import settings from the app config
from pathlib import Path

# Ensure project root is on sys.path so `from app...` imports work when this
# script is run directly from the `scripts/` directory.
PROJECT_ROOT = Path(__file__).resolve()
for _ in range(5):
    if (PROJECT_ROOT / "app").exists() and (PROJECT_ROOT / "requirements.txt").exists():
        break
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TARGET_TABLES = [
    "sale",
    "repair",
    "customerbalance",
]

SQL_CHECK_TABLE = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :db AND table_name = :table"
SQL_CHECK_COLUMN = "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = :db AND table_name = :table AND column_name = :column"


def rand_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main(dry_run: bool = True, apply: bool = False, drop_customer: bool = False):
    db_url = settings.DATABASE_URL_SYNC
    if not db_url:
        print("DATABASE_URL_SYNC not configured in settings. Aborting.")
        sys.exit(1)

    engine = create_engine(db_url)

    # Extract DB name from the URL for information_schema checks (MySQL-like)
    # This is a simple heuristic: url like mysql+pymysql://user:pass@host/dbname
    db_name = db_url.split("/")[-1].split("?")[0]

    with engine.connect() as conn:
        # 1) Check customer table exists
        r = conn.execute(text(SQL_CHECK_TABLE), {"db": db_name, "table": "customer"})
        if r.scalar() == 0:
            print("No `customer` table found in database. Nothing to migrate.")
            return

        # 2) Inspect customer columns
        col_check = conn.execute(text(SQL_CHECK_COLUMN), {"db": db_name, "table": "customer", "column": "phone"})
        has_phone = col_check.scalar() > 0
        col_check_pw = conn.execute(text(SQL_CHECK_COLUMN), {"db": db_name, "table": "customer", "column": "hashed_password"})
        has_hashed_pw = col_check_pw.scalar() > 0

        if not has_phone:
            print("Customer table has no `phone` column — this script expects `phone` to be present.")
            print("Please adapt the script to match your actual customer schema.")
            return

        # 3) Determine target column for each table. If an existing
        # `customer_id` column is present we will overwrite it with the
        # migrated user id values (this is compatible with your current
        # schema where sale.customer_id references customer.id). Otherwise
        # we'll create/populate a new `user_id` column.
        target_cols = {}
        for table in TARGET_TABLES:
            if conn.execute(text(SQL_CHECK_COLUMN), {"db": db_name, "table": table, "column": "customer_id"}).scalar() > 0:
                target_cols[table] = "customer_id"
                print(f"Table {table}: will reuse existing column 'customer_id' for user mapping")
            else:
                # fallback to user_id
                col = "user_id"
                col_exists = conn.execute(text(SQL_CHECK_COLUMN), {"db": db_name, "table": table, "column": col}).scalar() > 0
                print(f"Table {table}: {col} exists? {col_exists}")
                if not col_exists and apply:
                    print(f"Adding column {col} to {table} (nullable INT)")
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} INT NULL"))
                target_cols[table] = col

        # 4) Read customers
        customers = conn.execute(text("SELECT id, name, phone" + (", hashed_password" if has_hashed_pw else "") + " FROM customer")).fetchall()
        print(f"Found {len(customers)} customers to migrate")

        if dry_run and not apply:
            print("Dry run mode. Use --apply to perform changes. Exiting.")
            return

        # 5) Insert users and map
        created_users = []
        for row in customers:
            cust_id = row[0]
            name = row[1]
            phone = row[2]
            hashed_pw = row[3] if has_hashed_pw else None

            username = phone if phone else f"cust_{cust_id}"
            email = f"{username}@customers.local"

            if not hashed_pw:
                clear_pw = rand_password(12)
                hashed_pw = pwd_context.hash(clear_pw)
                print(f"Customer id={cust_id} -> temporary password: {clear_pw}")
            else:
                # We assume hashed_pw is already a bcrypt-style hash acceptable by passlib
                pass

            # Insert user (basic fields). Adjust columns if you use different schema.
            insert_sql = text(
                "INSERT INTO `user` (username, email, role, phone, hashed_password, created_at, updated_at)"
                " VALUES (:username, :email, 'customer', :phone, :hashed_password, :now, :now)"
            )
            now = datetime.utcnow()
            try:
                res = conn.execute(insert_sql, {"username": username, "email": email, "phone": phone, "hashed_password": hashed_pw, "now": now})
                # For MySQL, lastrowid should hold the inserted id
                new_user_id = res.lastrowid
                print(f"Inserted user id={new_user_id} for customer id={cust_id}")
                created_users.append((cust_id, new_user_id))

                # Update target tables mapping customer_id -> target_col
                for table in TARGET_TABLES:
                    col = target_cols.get(table)
                    update_sql = text(f"UPDATE {table} SET {col} = :uid WHERE customer_id = :cid")
                    conn.execute(update_sql, {"uid": new_user_id, "cid": cust_id})

            except SQLAlchemyError as e:
                print(f"Failed to insert user for customer {cust_id}: {e}")
                conn.rollback()
                raise

        # 6) Add foreign key constraints to new columns
        for table, col in target_cols.items():
            fk_name = f"fk_{table}_{col}_user"
            # Only add FK if not exists (simple attempt)
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} FOREIGN KEY ({col}) REFERENCES `user`(id)"))
                print(f"Added FK {fk_name} on {table}({col}) -> user(id)")
            except SQLAlchemyError as e:
                print(f"Could not add FK on {table}.{col}: {e}")

        if drop_customer:
            # Verify no FK references remain (user should inspect carefully before dropping)
            try:
                conn.execute(text("DROP TABLE customer"))
                print("Dropped `customer` table.")
            except SQLAlchemyError as e:
                print(f"Failed to drop customer table: {e}")

        print("Migration complete. Verify data carefully before deleting old columns or tables.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate customers into users (conservative).")
    parser.add_argument("--apply", action="store_true", help="Perform the changes (default is dry-run)")
    parser.add_argument("--drop-customer", action="store_true", help="Drop the old customer table after migration (use with caution)")
    args = parser.parse_args()

    main(dry_run=not args.apply, apply=args.apply, drop_customer=args.drop_customer)
