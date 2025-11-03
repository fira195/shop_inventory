from typing import List, Optional
from pydantic import BaseModel
from datetime import date
from app.model.models import PaymentMethod

class CashLedgerBase(BaseModel):
    date: date
    total_sales_cash: float
    total_sales_telebirr: float
    total_sales_bank: float
    total_expenses: float

class CashLedgerCreate(CashLedgerBase):
    pass

class CashLedgerResponse(CashLedgerBase):
    id: int
    opening_balance: float
    closing_balance: float
    usd_rate: float

    class Config:
        orm_mode = True

class ExpenseBase(BaseModel):
    date: date
    category_id: int
    amount: float
    payment_method: PaymentMethod
    notes: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseResponse(ExpenseBase):
    id: int
    entered_by: Optional[int]

    class Config:
        orm_mode = True