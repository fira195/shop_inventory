from typing import Optional
from pydantic import BaseModel
from datetime import datetime, date


class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(CustomerBase):
    name: Optional[str] = None

class CustomerRead(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime

class CustomerResponse(CustomerBase):
    id: int

    class Config:
        orm_mode = True