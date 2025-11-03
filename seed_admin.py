#!/usr/bin/env python3
"""
Script to seed an admin user in the Shop Inventory Master database
"""
import os
import sys
from pathlib import Path

# Make running this script directly work (so `from app...` imports resolve).
PROJECT_ROOT = Path(__file__).resolve()
for _ in range(5):
    if (PROJECT_ROOT / "app").exists() and (PROJECT_ROOT / "requirements.txt").exists():
        break
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from sqlmodel import Session, create_engine, select
from app.config.config import settings
from app.model.models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed_admin(username: str, password: str, email: str, phone: str = None, name: str = None, force: bool = False, auto_yes: bool = False):
    """Seed an admin user with the provided username, password, email, phone, and name.

    If `force` is True the script will delete any existing user matching the given
    username OR email before creating the new admin. When `auto_yes` is False the
    script will prompt for confirmation before deleting.
    """
    # Prefer a synchronous DB URL for this script. If a sync URL is not
    # configured, derive one from the async URL by switching the driver to
    # a pymysql sync driver (best-effort). This avoids greenlet_spawn errors
    # when SQLAlchemy attempts to obtain a raw DB-API connection with an
    # async dialect such as aiomysql.
    db_url = getattr(settings, "DATABASE_URL_SYNC", None) or getattr(settings, "DATABASE_URL", None)
    if not db_url:
        print("❌ DATABASE_URL_SYNC or DATABASE_URL not found in settings.")
        print("Please ensure your .env file is configured correctly.")
        exit(1)

    if "+aiomysql" in db_url or "+asyncmy" in db_url:
        if not getattr(settings, "DATABASE_URL_SYNC", None):
            derived = db_url.replace("+aiomysql", "+pymysql").replace("+asyncmy", "+pymysql")
            print("⚠️  Derived sync DB URL by replacing async driver with pymysql (best-effort):")
            print(f"   {derived.split('@')[-1]}")
            db_url = derived

    engine = create_engine(db_url, echo=True)
    with Session(engine) as session:
        # Find any existing users that match the username or email
        existing = session.exec(select(User).where((User.username == username) | (User.email == email))).all()
        if existing and not force:
            print("⚠️ Admin user (or a user with that email) already exists:")
            for u in existing:
                print(f" - {u.username} <{u.email}> (id={u.id})")
            print("If you want to replace them, re-run with --force")
            return

        if existing and force:
            if not auto_yes:
                ans = input(f"About to DELETE {len(existing)} user(s) matching username/email. Continue? [y/N]: ")
                if ans.strip().lower() not in ("y", "yes"):
                    print("Aborted by user.")
                    return
            for u in existing:
                print(f"Deleting user {u.username} <{u.email}> (id={u.id})")
                session.delete(u)
            session.commit()

        # bcrypt has a 72-byte input limit; truncate long passwords to avoid errors
        try:
            pw_bytes = password.encode("utf-8") if isinstance(password, str) else password
        except Exception:
            pw_bytes = str(password).encode("utf-8")
        if len(pw_bytes) > 72:
            print("⚠️ Password is longer than 72 bytes; truncating to bcrypt limit (72 bytes).")
            pw_bytes = pw_bytes[:72]
            try:
                password = pw_bytes.decode("utf-8", errors="ignore")
            except Exception:
                password = pw_bytes.decode("utf-8", errors="replace")

        hashed_password = pwd_context.hash(password)
        admin_user = User(
            username=username,
            email=email,
            phone=phone,
            name=name,
            hashed_password=hashed_password,
            role="admin",
        )
        session.add(admin_user)
        session.commit()
        print(f"✅ Admin user created with username: {username}, email: {email}, phone: {phone or 'None'}, name: {name or 'None'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed admin user")
    parser.add_argument("--username", type=str, default="admin", help="Admin username")
    parser.add_argument("--password", type=str, default="Admin!2025", help="Admin password")
    parser.add_argument("--email", type=str, default="admin@example.com", help="Admin email")
    parser.add_argument("--phone", type=str, default=None, help="Admin phone (optional)")
    parser.add_argument("--name", type=str, default=None, help="Admin name (optional)")
    parser.add_argument("--force", action="store_true", help="If set, delete any existing user with the same username or email before creating the admin")
    parser.add_argument("--yes", dest="yes", action="store_true", help="Skip confirmation prompt when using --force")
    args = parser.parse_args()

    if not settings.DATABASE_URL:
        print("❌ DATABASE_URL not found in settings.")
        print("Please ensure your .env file is configured correctly.")
        exit(1)

    seed_admin(args.username, args.password, args.email, args.phone, args.name, force=args.force, auto_yes=args.yes)
