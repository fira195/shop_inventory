from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List
from app.db.session import get_session
from app.auth.auth import get_current_user
from app.controller.cash_ledger_controller import create_cash_ledger, create_expense, get_cash_ledger, get_all_cash_ledgers, get_expense, get_all_expenses
from app.schemas.cash_ledger import CashLedgerCreate, CashLedgerResponse, ExpenseCreate, ExpenseResponse

router = APIRouter(prefix="/finance", tags=["Finance"])

@router.post("/cash-ledgers", response_model=CashLedgerResponse, status_code=status.HTTP_201_CREATED)
def create_cash_ledger_endpoint(ledger: CashLedgerCreate, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create cash ledgers"
        )
    return create_cash_ledger(db, ledger, current_user.id)

@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense_endpoint(expense: ExpenseCreate, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create expenses"
        )
    return create_expense(db, expense, current_user.id)

@router.get("/cash-ledgers/{ledger_id}", response_model=CashLedgerResponse)
def get_cash_ledger_endpoint(ledger_id: int, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    return get_cash_ledger(db, ledger_id)

@router.get("/cash-ledgers", response_model=List[CashLedgerResponse])
def get_all_cash_ledgers_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    return get_all_cash_ledgers(db, skip, limit)

@router.get("/expenses/{expense_id}", response_model=ExpenseResponse)
def get_expense_endpoint(expense_id: int, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    return get_expense(db, expense_id)

@router.get("/expenses", response_model=List[ExpenseResponse])
def get_all_expenses_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    return get_all_expenses(db, skip, limit)