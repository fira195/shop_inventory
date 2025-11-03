from typing import Optional
from pydantic import BaseModel
from datetime import date, datetime
from app.model.models import StockStatus, SourceType, MovementType

class StockItemBase(BaseModel):
    product_id: int
    sku: str
    serial_or_imei: str
    warranty_period: Optional[str] = None
    qty_on_hand: int = 1
    location: Optional[str] = None
    status: StockStatus
    supplier_id: Optional[int] = None
    source_type: SourceType
    invoice_no: Optional[str] = None
    purchase_date: Optional[date] = None
    cost_price: Optional[float] = None
    landed_cost: Optional[float] = None
    sale_price: Optional[float] = None
    usd_rate_at_purchase: Optional[float] = None
    notes: Optional[str] = None

class StockItemCreate(StockItemBase):
    pass

class StockItemResponse(StockItemBase):
    id: int
    created_by: Optional[int]
    created_at: datetime
    updated_by: Optional[int]
    updated_at: Optional[datetime]
    margin: Optional[float]

    class Config:
        orm_mode = True

class StockMovementBase(BaseModel):
    stock_item_id: int
    movement_type: MovementType
    quantity: int
    reference: Optional[str] = None
    reason: Optional[str] = None

class StockMovementCreate(StockMovementBase):
    pass

class StockMovementResponse(StockMovementBase):
    id: int
    performed_by: Optional[int]
    created_at: datetime

    class Config:
        orm_mode = True

class LowStockAlert(BaseModel):
    stock_item_id: int
    sku: str
    product_id: int
    qty_on_hand: int

class StockTransferCreate(BaseModel):
    stock_item_id: int
    quantity: int
    from_location: str
    to_location: str
    reference: Optional[str] = None
    reason: Optional[str] = None