from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import get_session
from app.model.models import StockItem
from sqlmodel import select

router = APIRouter(prefix="/branches", tags=["Branches"])

@router.get("/", response_model=list[dict])
async def list_branches(session: AsyncSession = Depends(get_session)):
    # derive distinct branches from StockItem.location
    results = await session.exec(select(StockItem.location).distinct())
    locations = [r for (r,) in results.all() if r]
    # assign ids as incremental integers for UI dropdowns
    branches = [{"id": i + 1, "name": loc} for i, loc in enumerate(locations)]
    return branches
