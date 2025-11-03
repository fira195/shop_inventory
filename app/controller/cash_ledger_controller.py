from typing import List
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.model.models import CashLedger, Expense, ExpenseCategory, USDExchangeRate
from app.schemas.cash_ledger import CashLedgerCreate, CashLedgerResponse, ExpenseCreate, ExpenseResponse
from datetime import date, datetime

def create_cash_ledger(db: Session, ledger_data: CashLedgerCreate, current_user_id: int) -> CashLedgerResponse:
    usd_rate = db.exec(
        select(USDExchangeRate).where(USDExchangeRate.date <= ledger_data.date)
        .order_by(USDExchangeRate.date.desc())
    ).first()
    usd_rate_value = usd_rate.rate if usd_rate else 1.0

    prev_ledger = db.exec(
        select(CashLedger).where(CashLedger.date < ledger_data.date)
        .order_by(CashLedger.date.desc())
    ).first()
    opening_balance = prev_ledger.closing_balance if prev_ledger else 0

    cash_ledger = CashLedger(
        date=ledger_data.date,
        opening_balance=opening_balance,
        total_sales_cash=ledger_data.total_sales_cash,
        total_sales_telebirr=ledger_data.total_sales_telebirr,
        total_sales_bank=ledger_data.total_sales_bank,
        total_expenses=ledger_data.total_expenses,
        closing_balance=(
            opening_balance +
            ledger_data.total_sales_cash +
            ledger_data.total_sales_telebirr +
            ledger_data.total_sales_bank -
            ledger_data.total_expenses
        ),
        usd_rate=usd_rate_value
    )
    db.add(cash_ledger)
    db.commit()
    db.refresh(cash_ledger)
    return CashLedgerResponse.model_validate(cash_ledger)

def create_expense(db: Session, expense_data: ExpenseCreate, current_user_id: int) -> ExpenseResponse:
    expense = Expense(
        date=expense_data.date,
        category_id=expense_data.category_id,
        amount=expense_data.amount,
        payment_method=expense_data.payment_method,
        notes=expense_data.notes,
        entered_by=current_user_id
    )
    db.add(expense)
    
    # Update CashLedger
    cash_ledger = db.exec(
        select(CashLedger).where(CashLedger.date == expense_data.date)
    ).first()
    if not cash_ledger:
        usd_rate = db.exec(
            select(USDExchangeRate).where(USDExchangeRate.date <= expense_data.date)
            .order_by(USDExchangeRate.date.desc())
        ).first()
        usd_rate_value = usd_rate.rate if usd_rate else 1.0
        prev_ledger = db.exec(
            select(CashLedger).where(CashLedger.date < expense_data.date)
            .order_by(CashLedger.date.desc())
        ).first()
        opening_balance = prev_ledger.closing_balance if prev_ledger else 0
        cash_ledger = CashLedger(
            date=expense_data.date,
            opening_balance=opening_balance,
            total_sales_cash=0.0,
            total_sales_telebirr=0.0,
            total_sales_bank=0.0,
            total_expenses=0.0,
            closing_balance=opening_balance,
            usd_rate=usd_rate_value
        )
        db.add(cash_ledger)
        db.flush()

    cash_ledger.total_expenses += expense_data.amount
    cash_ledger.closing_balance = (
        cash_ledger.opening_balance +
        cash_ledger.total_sales_cash +
        cash_ledger.total_sales_telebirr +
        cash_ledger.total_sales_bank -
        cash_ledger.total_expenses
    )
    db.add(cash_ledger)
    db.commit()
    db.refresh(expense)
    return ExpenseResponse.model_validate(expense)

def get_cash_ledger(db: Session, ledger_id: int) -> CashLedgerResponse:
    ledger = db.get(CashLedger, ledger_id)
    if not ledger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cash ledger not found"
        )
    return CashLedgerResponse.model_validate(ledger)

def get_all_cash_ledgers(db: Session, skip: int = 0, limit: int = 100) -> List[CashLedgerResponse]:
    ledgers = db.exec(select(CashLedger).offset(skip).limit(limit)).all()
    return [CashLedgerResponse.model_validate(ledger) for ledger in ledgers]

def get_expense(db: Session, expense_id: int) -> ExpenseResponse:
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    return ExpenseResponse.model_validate(expense)

def get_all_expenses(db: Session, skip: int = 0, limit: int = 100) -> List[ExpenseResponse]:
    expenses = db.exec(select(Expense).offset(skip).limit(limit)).all()
    return [ExpenseResponse.model_validate(expense) for expense in expenses]