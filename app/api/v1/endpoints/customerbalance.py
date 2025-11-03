from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import get_session
from app.model.models import CustomerBalance, CustomerBalanceCreate, CustomerBalanceRead
from app.api.v1.endpoints.user_router import get_current_user
from datetime import datetime

router = APIRouter(prefix="/customerbalances", tags=["Customer Balances"])

@router.post("/", response_model=CustomerBalanceRead, status_code=status.HTTP_201_CREATED)
async def create_customer_balance(
    balance: CustomerBalanceCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or managers can create customer balances"
        )
    db_balance = CustomerBalance(
        customer_id=balance.customer_id,
        balance=balance.balance,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_balance)
    await session.commit()
    await session.refresh(db_balance)
    return db_balance
