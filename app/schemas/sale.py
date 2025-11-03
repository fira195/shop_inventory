from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.model.models import PaymentMethod

class SaleItemBase(BaseModel):
    stock_item_id: int
    quantity: int
    unit_price: float
    subtotal: float

class SaleItemCreate(SaleItemBase):
    pass

class SaleItemResponse(SaleItemBase):
    id: int
    sale_id: int
    profit: float

    class Config:
        orm_mode = True

class SaleBase(BaseModel):
    customer_id: Optional[int] = None
    payment_method: PaymentMethod
    notes: Optional[str] = None

class SaleCreate(SaleBase):
    items: List[SaleItemCreate]

class SaleResponse(SaleBase):
    id: int
    sale_date: datetime
    sold_by: Optional[int]
    total_amount: float
    items: List[SaleItemResponse]

    class Config:
        orm_mode = True

class ReturnCreate(BaseModel):
    sale_id: int
    sale_item_ids: List[int]