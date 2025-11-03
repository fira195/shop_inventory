# app/db/session_sync.py
from sqlmodel import create_engine
from app.config.config import settings

# Use the SYNC database URL
engine = create_engine(settings.DATABASE_URL_SYNC, echo=True)
