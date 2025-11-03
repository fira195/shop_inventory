"""
Database migration script for Shop Inventory Master
Creates all tables defined in SQLModel models
"""
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so `from app...` imports work when this
# script is run directly (e.g. `python app/db/run_migration.py`). This avoids
# ModuleNotFoundError: No module named 'app'.
PROJECT_ROOT = Path(__file__).resolve()
for _ in range(5):
    if (PROJECT_ROOT / "app").exists() and (PROJECT_ROOT / "requirements.txt").exists():
        break
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import SQLModel, create_engine
from app.config.config import settings
from app.model.models import User  # Import all models
# Add other models as needed, e.g.:
# from app.model.models import Customer, Supplier, Product, PurchaseOrder, StockItem

def create_tables():
    """Create all database tables"""
    print("🚀 Running database migrations for Shop Inventory Master")
    # Prefer the synchronous DATABASE_URL_SYNC for DDL operations. If it's
    # not provided, try to derive a sync URL from the async one by swapping
    # async drivers (best-effort). Running create_all with an async driver
    # (e.g. mysql+aiomysql) causes the greenlet_spawn error seen previously.
    db_url = getattr(settings, "DATABASE_URL_SYNC", None) or getattr(settings, "DATABASE_URL", None)
    if not db_url:
        print("❌ DATABASE_URL_SYNC or DATABASE_URL not found in settings.")
        print("Please ensure your .env file is configured correctly.")
        exit(1)

    # If the configured URL appears to be async (aiomysql/asyncmy), try a
    # simple replacement to a synchronous driver (pymysql) as a fallback.
    if "+aiomysql" in db_url or "+asyncmy" in db_url:
        if not getattr(settings, "DATABASE_URL_SYNC", None):
            derived = db_url.replace("+aiomysql", "+pymysql").replace("+asyncmy", "+pymysql")
            print("⚠️  Using derived sync DB URL by replacing async driver with pymysql (best-effort):")
            print(f"   {derived.split('@')[-1]}")
            db_url = derived
    else:
        print(f"📊 Database: {db_url.split('@')[-1]}")
    print("-" * 50)

    try:
        engine = create_engine(db_url, echo=True)
        SQLModel.metadata.create_all(engine)
        print("\n✅ Tables created successfully!")
        print("Tables created:")
        for table in SQLModel.metadata.tables.keys():
            print(f"  - {table}")
    except Exception as e:
        print(f"❌ Error creating tables: {str(e)}")
        print("Please check your database connection and MySQL permissions.")
        raise

if __name__ == "__main__":
    if not settings.DATABASE_URL:
        print("❌ DATABASE_URL not found in settings.")
        print("Please ensure your .env file is configured correctly.")
        exit(1)
    create_tables()