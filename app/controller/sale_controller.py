from typing import List
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.model.models import Sale, SaleItem, StockItem, CashLedger, PaymentMethod, USDExchangeRate
from app.schemas.sale import SaleCreate, SaleResponse, SaleItemCreate, ReturnCreate
from datetime import date, datetime
from decimal import Decimal

def create_sale(db: Session, sale_data: SaleCreate, current_user_id: int) -> SaleResponse:
    # Validate stock availability
    for item in sale_data.items:
        stock = db.get(StockItem, item.stock_item_id)
        if not stock or stock.qty_on_hand < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for item {item.stock_item_id}"
            )
    
    # Create Sale
    sale = Sale(
        sold_by=current_user_id,
        customer_id=sale_data.customer_id,
        payment_method=sale_data.payment_method,
        total_amount=sum(item.subtotal for item in sale_data.items),
        notes=sale_data.notes
    )
    db.add(sale)
    db.flush()  # Get sale.id before committing

    # Create SaleItems and update StockItems
    sale_items = []
    for item in sale_data.items:
        stock = db.get(StockItem, item.stock_item_id)
        sale_item = SaleItem(
            sale_id=sale.id,
            stock_item_id=item.stock_item_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=item.subtotal,
            profit=item.subtotal - (stock.cost_price or 0) * item.quantity
        )
        stock.qty_on_hand -= item.quantity
        stock.status = "sold" if stock.qty_on_hand == 0 else stock.status
        sale_items.append(sale_item)
        db.add(sale_item)
        db.add(stock)
    
    # Update CashLedger
    today = date.today()
    cash_ledger = db.exec(
        select(CashLedger).where(CashLedger.date == today)
    ).first()
    
    # Fetch USD exchange rate
    usd_rate = db.exec(
        select(USDExchangeRate).where(USDExchangeRate.date <= today)
        .order_by(USDExchangeRate.date.desc())
    ).first()
    usd_rate_value = usd_rate.rate if usd_rate else 1.0
    
    if not cash_ledger:
        # Assume previous day's closing balance or 0 if none
        prev_ledger = db.exec(
            select(CashLedger).where(CashLedger.date < today)
            .order_by(CashLedger.date.desc())
        ).first()
        opening_balance = prev_ledger.closing_balance if prev_ledger else 0
        cash_ledger = CashLedger(
            date=today,
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

    # Update cash ledger based on payment method
    sale_amount = float(sale.total_amount)
    if sale.payment_method == PaymentMethod.cash:
        cash_ledger.total_sales_cash += sale_amount
    elif sale.payment_method == PaymentMethod.telebirr:
        cash_ledger.total_sales_telebirr += sale_amount
    elif sale.payment_method == PaymentMethod.bank:
        cash_ledger.total_sales_bank += sale_amount
    cash_ledger.closing_balance = (
        cash_ledger.opening_balance +
        cash_ledger.total_sales_cash +
        cash_ledger.total_sales_telebirr +
        cash_ledger.total_sales_bank -
        cash_ledger.total_expenses
    )
    cash_ledger.usd_rate = usd_rate_value
    db.add(cash_ledger)

    db.commit()
    db.refresh(sale)
    return SaleResponse.model_validate(sale)

def process_return(db: Session, return_data: ReturnCreate, current_user_id: int) -> SaleResponse:
    sale = db.get(Sale, return_data.sale_id)
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found"
        )
    
    # Process return for specified items
    for item_id in return_data.sale_item_ids:
        sale_item = db.get(SaleItem, item_id)
        if not sale_item or sale_item.sale_id != sale.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sale item {item_id}"
            )
        stock = db.get(StockItem, sale_item.stock_item_id)
        if not stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock item {sale_item.stock_item_id} not found"
            )
        stock.qty_on_hand += sale_item.quantity
        stock.status = "available"
        sale.total_amount -= sale_item.subtotal
        db.delete(sale_item)
        db.add(stock)

    # Update CashLedger
    today = date.today()
    cash_ledger = db.exec(
        select(CashLedger).where(CashLedger.date == today)
    ).first()
    
    # Fetch USD exchange rate
    usd_rate = db.exec(
        select(USDExchangeRate).where(USDExchangeRate.date <= today)
        .order_by(USDExchangeRate.date.desc())
    ).first()
    usd_rate_value = usd_rate.rate if usd_rate else 1.0
    
    if not cash_ledger:
        prev_ledger = db.exec(
            select(CashLedger).where(CashLedger.date < today)
            .order_by(CashLedger.date.desc())
        ).first()
        opening_balance = prev_ledger.closing_balance if prev_ledger else 0
        cash_ledger = CashLedger(
            date=today,
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

    return_amount = sum(
        db.get(SaleItem, item_id).subtotal 
        for item_id in return_data.sale_item_ids
    )
    if sale.payment_method == PaymentMethod.cash:
        cash_ledger.total_sales_cash -= float(return_amount)
    elif sale.payment_method == PaymentMethod.telebirr:
        cash_ledger.total_sales_telebirr -= float(return_amount)
    elif sale.payment_method == PaymentMethod.bank:
        cash_ledger.total_sales_bank -= float(return_amount)
    cash_ledger.closing_balance = (
        cash_ledger.opening_balance +
        cash_ledger.total_sales_cash +
        cash_ledger.total_sales_telebirr +
        cash_ledger.total_sales_bank -
        cash_ledger.total_expenses
    )
    cash_ledger.usd_rate = usd_rate_value
    db.add(cash_ledger)

    db.add(sale)
    db.commit()
    db.refresh(sale)
    return SaleResponse.model_validate(sale)

def get_sale(db: Session, sale_id: int) -> SaleResponse:
    sale = db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found"
        )
    return SaleResponse.model_validate(sale)

def get_all_sales(db: Session, skip: int = 0, limit: int = 100) -> List[SaleResponse]:
    sales = db.exec(select(Sale).offset(skip).limit(limit)).all()
    return [SaleResponse.model_validate(sale) for sale in sales]