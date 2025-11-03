from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Optional
from app.db.session import get_session
from app.api.v1.endpoints.user_router import get_current_user
from app.controller.report_controller import get_sales_summary, get_stock_status, get_financial_summary, get_customer_activity, get_purchase_order_status, get_stock_movement_history
from app.controller.report_controller import get_sales_trends
from app.controller.report_controller import get_sales_transactions
from app.controller.report_controller import get_today_sales, get_pending_repairs_count, get_low_stock_count, get_current_cash_balance, get_sales_overview
from functools import partial
from app.schemas.report import SalesSummaryResponse, StockStatusResponse, FinancialSummaryResponse, CustomerActivityResponse, PurchaseOrderStatusResponse, StockMovementHistoryResponse
from app.schemas.report import SalesTransactionsResponse
from app.model.models import PaymentMethod
from app.schemas.user import UserRole
from datetime import date, timedelta

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/sales-summary", response_model=SalesSummaryResponse)
async def get_sales_summary_endpoint(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    payment_method: Optional[PaymentMethod] = None,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Only admins and managers allowed
    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can access sales summary reports"
        )
    # run the sync controller function in a sync session
    result = await db.run_sync(partial(get_sales_summary, start_date=start_date, end_date=end_date, payment_method=payment_method))
    return result

@router.get("/stock-status", response_model=StockStatusResponse)
async def get_stock_status_endpoint(
    low_stock_threshold: int = 5,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can access stock status reports"
        )
    return await db.run_sync(partial(get_stock_status, low_stock_threshold))

@router.get("/financial-summary", response_model=FinancialSummaryResponse)
async def get_financial_summary_endpoint(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can access financial summary reports"
        )
    return await db.run_sync(partial(get_financial_summary, start_date=start_date, end_date=end_date))

@router.get("/customer-activity", response_model=CustomerActivityResponse)
async def get_customer_activity_endpoint(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can access customer activity reports"
        )
    return await db.run_sync(partial(get_customer_activity, start_date=start_date, end_date=end_date))

@router.get("/purchase-order-status", response_model=PurchaseOrderStatusResponse)
async def get_purchase_order_status_endpoint(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can access purchase order status reports"
        )
    return await db.run_sync(partial(get_purchase_order_status, start_date=start_date, end_date=end_date))

@router.get("/stock-movement-history", response_model=StockMovementHistoryResponse)
async def get_stock_movement_history_endpoint(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can access stock movement history reports"
        )
    return await db.run_sync(partial(get_stock_movement_history, start_date=start_date, end_date=end_date))


@router.get("/sales/trends")
async def get_sales_trends_endpoint(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """Return sales revenue trend (monthly) between start_date and end_date. Defaults to last 6 months."""
    from datetime import date as _date, timedelta
    # Default to last 6 months if not provided
    if end_date is None:
        end_date = _date.today()
    if start_date is None:
        # approximate 6 months by subtracting 180 days
        start_date = end_date - timedelta(days=180)

    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can access sales trends"
        )

    result = await db.run_sync(partial(get_sales_trends, start_date=start_date, end_date=end_date))
    return result


@router.get("/sales/transactions", response_model=SalesTransactionsResponse)
async def get_sales_transactions_endpoint(
    page: int = 1,
    limit: int = 5,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    branch: Optional[str] = None,
    category_id: Optional[int] = None,
    brand_id: Optional[int] = None,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    # default range to last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can access sales transactions"
        )

    result = await db.run_sync(partial(get_sales_transactions, start_date=start_date, end_date=end_date, branch=branch, category_id=category_id, brand_id=brand_id, page=page, limit=limit))
    return result


@router.get("/sales/export")
async def export_sales_report(
    format: str = "csv",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    branch: Optional[str] = None,
    category_id: Optional[int] = None,
    brand_id: Optional[int] = None,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """Export sales transactions as CSV (format=csv). Other formats may be implemented later."""
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can export sales reports"
        )

    # fetch all matching transactions (no pagination)
    # use a very large limit to pull all rows; for large datasets implement streaming from DB
    result = await db.run_sync(partial(get_sales_transactions, start_date=start_date, end_date=end_date, branch=branch, category_id=category_id, brand_id=brand_id, page=1, limit=10_000_000))

    # build CSV
    import io, csv
    from fastapi.responses import StreamingResponse

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "invoice_no", "product", "category", "quantity", "unit_price", "total"])
    for t in result.get("transactions", []):
        writer.writerow([t["date"].isoformat() if hasattr(t["date"], "isoformat") else t["date"], t["invoice_no"], t["product"], t.get("category"), t["quantity"], t["unit_price"], t["total"]])

    output.seek(0)
    media_type = "text/csv"
    filename = f"sales_report_{start_date.isoformat()}_to_{end_date.isoformat()}.csv"
    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}

    return StreamingResponse(output, media_type=media_type, headers=headers)


@router.get("/dashboard/summary")
async def dashboard_summary(db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins and managers can access dashboard summary")
    # gather metrics via sync controller functions
    today_sales = await db.run_sync(get_today_sales)
    pending_repairs = await db.run_sync(get_pending_repairs_count)
    low_stock_items = await db.run_sync(lambda s: get_low_stock_count(s, 5))
    cash_balance = await db.run_sync(get_current_cash_balance)
    return {
        "today_sales": today_sales,
        "pending_repairs": pending_repairs,
        "low_stock_items": low_stock_items,
        "cash_balance": cash_balance
    }


@router.get("/sales/overview")
async def sales_overview(days: int = 7, db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role", "").lower() not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins and managers can access sales overview")
    result = await db.run_sync(lambda s: get_sales_overview(s, days))
    return result