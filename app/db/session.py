# app/db/session.py
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker

from app.config.config import settings

# Note: We add pool_recycle=3600 (1 hour) as a best practice for MySQL
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL, 
    echo=True, 
    future=True,
    pool_recycle=3600
)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    # from models.product import Product, StockItem
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

from typing import AsyncGenerator

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session