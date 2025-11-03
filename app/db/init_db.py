# app/db/init_db.py
from sqlmodel import SQLModel, create_engine
from app.model.models import User
from app.config.config import settings

def init_db():
    print("Creating all tables...")
    engine = create_engine(settings.DATABASE_URL_SYNC, echo=True)  # ⚡ Use sync engine
    SQLModel.metadata.create_all(engine)
    print("✅ Tables created successfully!")

if __name__ == "__main__":
    init_db()
