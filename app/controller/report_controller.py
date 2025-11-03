from typing import List, Optional
from fastapi import HTTPException, status
from sqlmodel import Session, select, func
from sqlalchemy.sql import and_
from app.model.models import Sale, SaleItem, StockItem, Product, Category, Brand, CashLedger, Expense, ExpenseCategory, PaymentMethod, User, Repair, PurchaseOrder, PurchaseOrderItem, Supplier, StockMovement
from app.schemas.report import SalesSummaryResponse, SalesSummaryItem, StockStatusResponse, StockStatusItem, FinancialSummaryResponse, FinancialSummaryItem, ExpenseBreakdownItem, CustomerActivityResponse, CustomerActivityItem, PurchaseOrderStatusResponse, PurchaseOrderStatusItem, StockMovementHistoryResponse, StockMovementHistoryItem
from datetime import date
from typing import Dict, Any
from datetime import datetime, date, timedelta

def _iter_months(start_date: date, end_date: date):
    """Yield (year, month, date_obj) for each month between start_date and end_date inclusive."""
    from datetime import date as _date
    y = start_date.year
    m = start_date.month
    while True:
        yield (y, m, _date(y, m, 1))
        if y == end_date.year and m == end_date.month:
            break
        m += 1
        if m > 12:
            m = 1
            y += 1


def get_sales_trends(db: Session, start_date: date, end_date: date):
    """Return month-by-month total revenue between start_date and end_date.

    Returns a dict with keys: period (human string), trend_data (list of {month,revenue}), growth_rate (monthly CAGR %)
    """
    validate_date_range(start_date, end_date)

    # Build month list
    months = []
    for y, m, dt in _iter_months(start_date, end_date):
        months.append((y, m, dt))

    # Aggregate revenue per year/month
    year_expr = func.year(Sale.sale_date).label("y")
    month_expr = func.month(Sale.sale_date).label("m")
    revenue_expr = func.sum(Sale.total_amount).label("revenue")

    query = (
        select(year_expr, month_expr, revenue_expr)
        .where(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
        .group_by(year_expr, month_expr)
        .order_by(year_expr, month_expr)
    )
    results = db.exec(query).all()

    rev_map = {(int(r.y), int(r.m)): float(r.revenue or 0.0) for r in results}

    trend_data = []
    for (y, m, dt) in months:
        revenue = rev_map.get((y, m), 0.0)
        trend_data.append({"month": dt.strftime("%b"), "revenue": revenue})

    # Compute compound monthly growth rate (CAGR) from first non-zero to last
    revenues = [item["revenue"] for item in trend_data]
    first = revenues[0] if revenues else 0.0
    last = revenues[-1] if revenues else 0.0
    n_periods = max(len(revenues) - 1, 1)
    growth_rate = 0.0
    try:
        if first > 0 and len(revenues) > 1:
            growth_rate = (last / first) ** (1 / n_periods) - 1
            growth_rate = round(growth_rate * 100, 2)
        else:
            growth_rate = 0.0
    except Exception:
        growth_rate = 0.0

    # period string like "Jan-Jun 2023" or "Dec 2022 - Feb 2023"
    if start_date.year == end_date.year and start_date.month != end_date.month:
        period = f"{start_date.strftime('%b')}-{end_date.strftime('%b %Y')}"
    else:
        period = f"{start_date.strftime('%b %Y')} - {end_date.strftime('%b %Y')}"

    return {
        "period": period,
        "trend_data": trend_data,
        "growth_rate": growth_rate,
    }

def validate_date_range(start_date: date, end_date: date):
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before or equal to end date"
        )
    if end_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be in the future"
        )

def get_sales_summary(db: Session, start_date: date, end_date: date, payment_method: Optional[PaymentMethod] = None) -> SalesSummaryResponse:
    validate_date_range(start_date, end_date)
    query = (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            func.sum(SaleItem.quantity).label("total_quantity"),
            func.sum(SaleItem.subtotal).label("total_revenue"),
            func.sum(SaleItem.profit).label("total_profit")
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .join(StockItem, SaleItem.stock_item_id == StockItem.id)
        .join(Product, StockItem.product_id == Product.id)
        .where(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
    )

    if payment_method:
        query = query.where(Sale.payment_method == payment_method)

    query = query.group_by(Product.id, Product.name)
    results = db.exec(query).all()

    total_revenue = sum(result.total_revenue for result in results)
    total_profit = sum(result.total_profit for result in results)

    items = [
        SalesSummaryItem(
            product_id=result.product_id,
            product_name=result.product_name,
            total_quantity=result.total_quantity,
            total_revenue=result.total_revenue,
            total_profit=result.total_profit
        )
        for result in results
    ]

    return SalesSummaryResponse(
        start_date=start_date,
        end_date=end_date,
        payment_method=payment_method,
        total_revenue=total_revenue,
        total_profit=total_profit,
        items=items
    )

def get_stock_status(db: Session, low_stock_threshold: int = 5) -> StockStatusResponse:
    query = (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            StockItem.sku,
            StockItem.qty_on_hand,
            (StockItem.sale_price * StockItem.qty_on_hand).label("stock_value")
        )
        .join(Product, StockItem.product_id == Product.id)
    )

    results = db.exec(query).all()

    items = [
        StockStatusItem(
            product_id=result.product_id,
            product_name=result.product_name,
            sku=result.sku,
            qty_on_hand=result.qty_on_hand,
            stock_value=result.stock_value or 0.0,
            is_low_stock=result.qty_on_hand < low_stock_threshold
        )
        for result in results
    ]

    total_stock_value = sum(item.stock_value for item in items)

    return StockStatusResponse(
        total_stock_value=total_stock_value,
        low_stock_threshold=low_stock_threshold,
        items=items
    )

def get_financial_summary(db: Session, start_date: date, end_date: date) -> FinancialSummaryResponse:
    validate_date_range(start_date, end_date)
    ledger_query = select(CashLedger).where(
        and_(CashLedger.date >= start_date, CashLedger.date <= end_date)
    )
    ledgers = db.exec(ledger_query).all()

    expense_query = (
        select(
            ExpenseCategory.id.label("category_id"),
            ExpenseCategory.name.label("category_name"),
            func.sum(Expense.amount).label("total_amount")
        )
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(Expense.date >= start_date, Expense.date <= end_date)
        .group_by(ExpenseCategory.id, ExpenseCategory.name)
    )
    expense_results = db.exec(expense_query).all()

    total_sales = sum(
        ledger.total_sales_cash + ledger.total_sales_telebirr + ledger.total_sales_bank
        for ledger in ledgers
    )
    total_expenses = sum(ledger.total_expenses for ledger in ledgers)
    net_cash_flow = total_sales - total_expenses

    ledger_items = [
        FinancialSummaryItem(
            date=ledger.date,
            opening_balance=ledger.opening_balance,
            total_sales_cash=ledger.total_sales_cash,
            total_sales_telebirr=ledger.total_sales_telebirr,
            total_sales_bank=ledger.total_sales_bank,
            total_expenses=ledger.total_expenses,
            closing_balance=ledger.closing_balance,
            usd_rate=ledger.usd_rate
        )
        for ledger in ledgers
    ]

    expense_items = [
        ExpenseBreakdownItem(
            category_id=result.category_id,
            category_name=result.category_name,
            total_amount=result.total_amount
        )
        for result in expense_results
    ]

    return FinancialSummaryResponse(
        start_date=start_date,
        end_date=end_date,
        total_sales=total_sales,
        total_expenses=total_expenses,
        net_cash_flow=net_cash_flow,
        cash_ledgers=ledger_items,
        expense_breakdown=expense_items
    )

def get_customer_activity(db: Session, start_date: date, end_date: date) -> CustomerActivityResponse:
    validate_date_range(start_date, end_date)
    # Use `User` rows with role='customer' instead of a separate Customer table
    sales_query = (
        select(
            User.id.label("customer_id"),
            User.username.label("customer_name"),
            func.sum(Sale.total_amount).label("total_sales"),
            func.count(Sale.id).label("total_sales_count")
        )
        .join(Sale, Sale.customer_id == User.id)
        .where(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
        .group_by(User.id, User.username)
    )

    repairs_query = (
        select(
            User.id.label("customer_id"),
            User.username.label("customer_name"),
            func.sum(Repair.deposit_amount).label("total_repairs"),
            func.count(Repair.id).label("total_repairs_count")
        )
        .join(Repair, Repair.customer_id == User.id)
        .where(Repair.received_date >= start_date, Repair.received_date <= end_date)
        .group_by(User.id, User.username)
    )

    sales_results = db.exec(sales_query).all()
    repairs_results = db.exec(repairs_query).all()

    customer_data = {}
    for sale in sales_results:
        customer_data[sale.customer_id] = {
            "customer_id": sale.customer_id,
            "customer_name": sale.customer_name,
            "total_sales": sale.total_sales or 0.0,
            "total_sales_count": sale.total_sales_count or 0,
            "total_repairs": 0.0,
            "total_repairs_count": 0
        }
    for repair in repairs_results:
        if repair.customer_id in customer_data:
            customer_data[repair.customer_id]["total_repairs"] = repair.total_repairs or 0.0
            customer_data[repair.customer_id]["total_repairs_count"] = repair.total_repairs_count or 0
        else:
            customer_data[repair.customer_id] = {
                "customer_id": repair.customer_id,
                "customer_name": repair.customer_name,
                "total_sales": 0.0,
                "total_sales_count": 0,
                "total_repairs": repair.total_repairs or 0.0,
                "total_repairs_count": repair.total_repairs_count or 0
            }

    items = [
        CustomerActivityItem(
            customer_id=data["customer_id"],
            customer_name=data["customer_name"],
            total_sales=data["total_sales"],
            total_sales_count=data["total_sales_count"],
            total_repairs=data["total_repairs"],
            total_repairs_count=data["total_repairs_count"]
        )
        for data in customer_data.values()
    ]

    total_sales = sum(data["total_sales"] for data in customer_data.values())
    total_repairs = sum(data["total_repairs"] for data in customer_data.values())

    return CustomerActivityResponse(
        start_date=start_date,
        end_date=end_date,
        total_sales=total_sales,
        total_repairs=total_repairs,
        items=items
    )

def get_purchase_order_status(db: Session, start_date: date, end_date: date) -> PurchaseOrderStatusResponse:
    validate_date_range(start_date, end_date)
    query = (
        select(
            PurchaseOrder.id.label("po_id"),
            PurchaseOrder.supplier_id,
            Supplier.name.label("supplier_name"),
            PurchaseOrder.status,
            PurchaseOrder.order_date,
            PurchaseOrder.expected_arrival,
            func.sum(PurchaseOrderItem.qty_ordered).label("total_ordered"),
            func.sum(PurchaseOrderItem.qty_received).label("total_received")
        )
        .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        .join(PurchaseOrderItem, PurchaseOrderItem.po_id == PurchaseOrder.id)
        .where(PurchaseOrder.order_date >= start_date, PurchaseOrder.order_date <= end_date)
        .group_by(PurchaseOrder.id, Supplier.name)
    )

    results = db.exec(query).all()

    items = [
        PurchaseOrderStatusItem(
            po_id=result.po_id,
            supplier_id=result.supplier_id,
            supplier_name=result.supplier_name,
            status=result.status,
            order_date=result.order_date,
            expected_arrival=result.expected_arrival,
            total_ordered=result.total_ordered,
            total_received=result.total_received
        )
        for result in results
    ]

    return PurchaseOrderStatusResponse(
        start_date=start_date,
        end_date=end_date,
        items=items
    )

def get_stock_movement_history(db: Session, start_date: date, end_date: date) -> StockMovementHistoryResponse:
    validate_date_range(start_date, end_date)
    query = (
        select(
            StockMovement.id.label("movement_id"),
            StockMovement.stock_item_id,
            StockItem.product_id,
            Product.name.label("product_name"),
            StockItem.sku,
            StockMovement.movement_type,
            StockMovement.quantity,
            StockItem.location,
            StockMovement.reference,
            StockMovement.reason,
            StockMovement.performed_by,
            StockMovement.created_at
        )
        .join(StockItem, StockMovement.stock_item_id == StockItem.id)
        .join(Product, StockItem.product_id == Product.id)
        .where(StockMovement.created_at >= start_date, StockMovement.created_at <= end_date)
    )

    results = db.exec(query).all()

    items = [
        StockMovementHistoryItem(
            movement_id=result.movement_id,
            stock_item_id=result.stock_item_id,
            product_id=result.product_id,
            product_name=result.product_name,
            sku=result.sku,
            movement_type=result.movement_type,
            quantity=result.quantity,
            location=result.location,
            reference=result.reference,
            reason=result.reason,
            performed_by=result.performed_by,
            created_at=result.created_at
        )
        for result in results
    ]

    return StockMovementHistoryResponse(
        start_date=start_date,
        end_date=end_date,
        items=items
    )


def get_sales_transactions(db: Session,
                           start_date: date,
                           end_date: date,
                           branch: Optional[str] = None,
                           category_id: Optional[int] = None,
                           brand_id: Optional[int] = None,
                           page: int = 1,
                           limit: int = 5) -> Dict[str, Any]:
    """Return paginated list of sale transaction rows (one row per SaleItem).

    Each transaction includes: date, invoice_no (formatted INV-xxxxx), product, category, quantity, unit_price, total
    """
    validate_date_range(start_date, end_date)

    # Base query joining SaleItem -> Sale -> StockItem -> Product -> Category -> Brand
    query = (
        select(
            Sale.id.label("sale_id"),
            Sale.sale_date.label("sale_date"),
            Product.name.label("product_name"),
            Category.name.label("category_name"),
            Brand.name.label("brand_name"),
            SaleItem.quantity.label("quantity"),
            SaleItem.unit_price.label("unit_price"),
            SaleItem.subtotal.label("total"),
            StockItem.location.label("location")
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .join(StockItem, SaleItem.stock_item_id == StockItem.id)
        .join(Product, StockItem.product_id == Product.id)
        .join(Category, Product.category_id == Category.id, isouter=True)
        .join(Brand, Product.brand_id == Brand.id, isouter=True)
        .where(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
        .order_by(Sale.sale_date.desc())
    )

    if branch:
        # branch is interpreted as StockItem.location
        query = query.where(StockItem.location == branch)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if brand_id:
        query = query.where(Product.brand_id == brand_id)

    # total count
    count_q = select(func.count()).select_from(query.subquery())
    count_res = db.exec(count_q).first()
    total = int(count_res[0] if count_res and count_res[0] is not None else 0)

    # pagination
    offset = (max(page, 1) - 1) * max(limit, 1)
    results = db.exec(query.offset(offset).limit(limit)).all()

    transactions = []
    for r in results:
        sale_dt = r.sale_date.date() if hasattr(r.sale_date, "date") else r.sale_date
        invoice_no = f"INV-{int(r.sale_id):05d}"
        transactions.append({
            "date": sale_dt,
            "invoice_no": invoice_no,
            "product": r.product_name,
            "category": r.category_name,
            "quantity": int(r.quantity),
            "unit_price": float(r.unit_price or 0.0),
            "total": float(r.total or 0.0)
        })

    return {"page": page, "limit": limit, "total": total, "transactions": transactions}


def get_today_sales(db: Session) -> float:
    today = date.today()
    q = select(func.coalesce(func.sum(Sale.total_amount), 0)).where(func.date(Sale.sale_date) == today)
    res = db.exec(q).first()
    return float(res[0] if res and res[0] is not None else 0.0)


def get_pending_repairs_count(db: Session) -> int:
    # Consider 'received' and 'in_progress' as pending
    q = select(func.count()).select_from(Repair).where(Repair.status.in_(["received", "in_progress"]))
    res = db.exec(q).first()
    return int(res[0] if res and res[0] is not None else 0)


def get_low_stock_count(db: Session, threshold: int = 5) -> int:
    q = select(func.count()).select_from(StockItem).where(StockItem.qty_on_hand < threshold)
    res = db.exec(q).first()
    return int(res[0] if res and res[0] is not None else 0)


def get_current_cash_balance(db: Session) -> float:
    # Get latest CashLedger by date and return closing_balance
    q = select(CashLedger).order_by(CashLedger.date.desc()).limit(1)
    ledger = db.exec(q).first()
    if not ledger:
        return 0.0
    return float(getattr(ledger, "closing_balance", 0.0) or 0.0)


def get_sales_overview(db: Session, days: int = 7) -> Dict[str, Any]:
    # Return daily totals for the last `days` days (including today)
    if days <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="days must be positive")
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    # sum per day
    q = (
        select(func.date(Sale.sale_date).label("d"), func.coalesce(func.sum(Sale.total_amount), 0).label("amount"))
        .where(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
        .group_by(func.date(Sale.sale_date))
        .order_by(func.date(Sale.sale_date))
    )
    rows = db.exec(q).all()
    amount_map = {r.d: float(r.amount or 0.0) for r in rows}

    data = []
    total = 0.0
    for i in range(days):
        d = start_date + timedelta(days=i)
        amt = amount_map.get(d, 0.0)
        total += amt
        data.append({"day": d.strftime("%a"), "amount": amt})

    # percentage change vs previous period of same length
    prev_start = start_date - timedelta(days=days)
    prev_end = start_date - timedelta(days=1)
    q2 = (
        select(func.coalesce(func.sum(Sale.total_amount), 0).label("amount"))
        .where(Sale.sale_date >= prev_start, Sale.sale_date <= prev_end)
    )
    prev_res = db.exec(q2).first()
    prev_total = float(prev_res[0] if prev_res and prev_res[0] is not None else 0.0)
    pct_change = 0.0
    try:
        if prev_total > 0:
            pct_change = round(((total - prev_total) / prev_total) * 100, 2)
        else:
            pct_change = 100.0 if total > 0 else 0.0
    except Exception:
        pct_change = 0.0

    return {"total_sales": total, "percentage_change": pct_change, "data": data}