from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
from app.model.models import POStatus

class SupplierBase(BaseModel):
    name: str

class SupplierCreate(SupplierBase):
    pass

class SupplierResponse(SupplierBase):
    id: int

    class Config:
        orm_mode = True

class PurchaseOrderItemBase(BaseModel):
    product_id: int
    qty_ordered: int
    unit_cost: float
    notes: Optional[str] = None

class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    pass

class PurchaseOrderItemResponse(PurchaseOrderItemBase):
    id: int
    po_id: int
    qty_received: int

    class Config:
        orm_mode = True

class PurchaseOrderBase(BaseModel):
    supplier_id: int
    branch_id: Optional[int] = None
    order_date: date
    expected_arrival: date
    usd_rate_at_order: float

class PurchaseOrderCreate(PurchaseOrderBase):
    items: List[PurchaseOrderItemCreate]

class PurchaseOrderResponse(PurchaseOrderBase):
    id: int
    status: POStatus
    created_by: Optional[int]
    created_at: datetime
    updated_by: Optional[int]
    updated_at: Optional[datetime]
    items: List[PurchaseOrderItemResponse]

    class Config:
        orm_mode = True

class PurchaseOrderReceiveItem(BaseModel):
    po_item_id: int
    qty_received: int
    sku: Optional[str] = None
    serial_or_imei: Optional[str] = None

class PurchaseOrderReceive(BaseModel):
    po_id: int
    items: List[PurchaseOrderReceiveItem]
    location: str
    invoice_no: Optional[str] = None
    purchase_date: Optional[date] = None