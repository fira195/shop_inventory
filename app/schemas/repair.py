from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.model.models import RepairStatus
from sqlmodel import SQLModel, Field


class RepairItemBase(BaseModel):
    product_id: int
    qty_used: int
    unit_cost: float
    unit_sale_price: Optional[float] = None

class RepairItemCreate(RepairItemBase):
    pass

class RepairItemResponse(RepairItemBase):
    id: int
    repair_id: int

    class Config:
        orm_mode = True

class RepairBase(BaseModel):
    customer_id: int = Field(foreign_key="user.id")
    device_description: str
    deposit_amount: float
    assigned_technician_id: Optional[int] = None
    due_date: datetime
    notes: Optional[str] = None

class RepairCreate(RepairBase):
    items: List[RepairItemCreate]
    customer_id: int
    description: str

class RepairResponse(RepairBase):
    id: int
    status: RepairStatus
    received_date: datetime
    completion_date: Optional[datetime]
    items: List[RepairItemResponse]

    class Config:
        orm_mode = True