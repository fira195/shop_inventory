from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import get_session
from app.auth.auth import get_current_user
from app.controller.repair_controller import create_repair, update_repair_status, get_repair, get_all_repairs
from app.schemas.repair import RepairCreate, RepairResponse
from app.model.models import Repair, RepairStatus


router = APIRouter(prefix="/repairs", tags=["Repairs"])

@router.post("/", response_model=RepairResponse, status_code=status.HTTP_201_CREATED)
async def create_repair(
    repair: RepairCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or managers can create repairs"
        )
    # Map schema fields to model fields (model uses device_description)
    db_repair = Repair(
        customer_id=repair.customer_id,
        device_description=getattr(repair, "description", getattr(repair, "device_description", "")),
        deposit_amount=getattr(repair, "deposit_amount", 0.0),
        assigned_technician_id=getattr(repair, "assigned_technician_id", None),
        due_date=getattr(repair, "due_date", datetime.utcnow()),
        notes=getattr(repair, "notes", None),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_repair)
    await session.commit()
    await session.refresh(db_repair)
    return db_repair

@router.put("/{repair_id}/status", response_model=RepairResponse)
def update_repair_status_endpoint(repair_id: int, status: RepairStatus, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update repair status"
        )
    return update_repair_status(db, repair_id, status, current_user.id)

@router.get("/{repair_id}", response_model=RepairResponse)
def get_repair_endpoint(repair_id: int, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    return get_repair(db, repair_id)

@router.get("/", response_model=List[RepairResponse])
def get_all_repairs_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    return get_all_repairs(db, skip, limit)