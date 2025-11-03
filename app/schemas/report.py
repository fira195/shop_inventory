from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
from app.model.models import PaymentMethod, POStatus, MovementType

class SalesSummaryItem(BaseModel):
    product_id: int
    product_name: str
    total_quantity: int
    total_revenue: float
    total_profit: float

class SalesSummaryResponse(BaseModel):
    start_date: date
    end_date: date
    payment_method: Optional[PaymentMethod] = None
    total_revenue: float
    total_profit: float
    items: List[SalesSummaryItem]

class StockStatusItem(BaseModel):
    product_id: int
    product_name: str
    sku: str
    qty_on_hand: int
    stock_value: float
    is_low_stock: bool

class StockStatusResponse(BaseModel):
    total_stock_value: float
    low_stock_threshold: int
    items: List[StockStatusItem]

class FinancialSummaryItem(BaseModel):
    date: date
    opening_balance: float
    total_sales_cash: float
    total_sales_telebirr: float
    total_sales_bank: float
    total_expenses: float
    closing_balance: float
    usd_rate: float

class ExpenseBreakdownItem(BaseModel):
    category_id: int
    category_name: str
    total_amount: float

class FinancialSummaryResponse(BaseModel):
    start_date: date
    end_date: date
    total_sales: float
    total_expenses: float
    net_cash_flow: float
    cash_ledgers: List[FinancialSummaryItem]
    expense_breakdown: List[ExpenseBreakdownItem]

class CustomerActivityItem(BaseModel):
    customer_id: int
    customer_name: str
    total_sales: float
    total_sales_count: int
    total_repairs: float
    total_repairs_count: int

class CustomerActivityResponse(BaseModel):
    start_date: date
    end_date: date
    total_sales: float
    total_repairs: float
    items: List[CustomerActivityItem]

class PurchaseOrderStatusItem(BaseModel):
    po_id: int
    supplier_id: int
    supplier_name: str
    status: POStatus
    order_date: date
    expected_arrival: date
    total_ordered: int
    total_received: int

class PurchaseOrderStatusResponse(BaseModel):
    start_date: date
    end_date: date
    items: List[PurchaseOrderStatusItem]

class StockMovementHistoryItem(BaseModel):
    movement_id: int
    stock_item_id: int
    product_id: int
    product_name: str
    sku: str
    movement_type: MovementType
    quantity: int
    location: str
    reference: Optional[str]
    reason: Optional[str]
    performed_by: Optional[int]
    created_at: datetime

class StockMovementHistoryResponse(BaseModel):
    start_date: date
    end_date: date
    items: List[StockMovementHistoryItem]


class TransactionItem(BaseModel):
    date: date
    invoice_no: str
    product: str
    category: Optional[str]
    quantity: int
    unit_price: float
    total: float


class SalesTransactionsResponse(BaseModel):
    page: int
    limit: int
    total: int
    transactions: List[TransactionItem]