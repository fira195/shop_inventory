from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlmodel import Session, select
from app.model.models import Sale, Product, StockItem, Receipt
from sqlmodel.ext.asyncio.session import AsyncSession

from typing import List, Optional
from app.db.session import get_session
from app.api.v1.endpoints.user_router import get_current_user
from app.controller.sale_controller import process_return, get_sale, get_all_sales, create_sale
from app.schemas.sale import SaleCreate, SaleResponse, ReturnCreate
from pydantic import BaseModel
from datetime import datetime
import json

router = APIRouter(prefix="/sales", tags=["Sales"])

@router.post("/", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
async def create_sale(
    sale: SaleCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or managers can create sales"
        )
    # Delegate to controller running in sync session
    result = await session.run_sync(lambda s: create_sale(s, sale, current_user["id"]))
    # create a receipt mapping for this sale
    # build receipt id: RCPT-YYYYMMDD-<sale.id:05d>
    try:
        receipt_id = f"RCPT-{result.sale_date.date().isoformat().replace('-', '')}-{int(result.id):05d}"
    except Exception:
        receipt_id = f"RCPT-{int(result.id):05d}"
    rec = Receipt(receipt_id=receipt_id, sale_id=result.id)
    session.add(rec)
    await session.commit()
    return result


class ReceiptItem(BaseModel):
    product_id: int
    quantity: int
    unit_price: float


class ReceiptCreate(BaseModel):
    customer_id: Optional[int]
    payment_method: str
    tendered_amount: Optional[float] = None
    discount: Optional[str] = None
    items: List[ReceiptItem]


@router.post("/receipts/", response_model=dict)
async def create_receipt_endpoint(receipt: ReceiptCreate, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or managers can create receipts")
    # Map product_id -> available stock_item
    sale_items = []
    for it in receipt.items:
        # find a stock item for product with enough qty_on_hand
        res = await session.exec(select(StockItem).where(StockItem.product_id == it.product_id, StockItem.qty_on_hand >= it.quantity))
        stock = res.first()
        if not stock:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient stock for product {it.product_id}")
        sale_items.append({
            "stock_item_id": stock.id,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "subtotal": round(it.quantity * it.unit_price, 2)
        })
    # build SaleCreate compatible object
    sale_payload = SaleCreate(
        customer_id=receipt.customer_id,
        payment_method=receipt.payment_method,
        notes=receipt.discount or None,
        items=[
            {
                "stock_item_id": si["stock_item_id"],
                "quantity": si["quantity"],
                "unit_price": si["unit_price"],
                "subtotal": si["subtotal"]
            }
            for si in sale_items
        ]
    )
    # call controller
    result = await session.run_sync(lambda s: create_sale(s, sale_payload, current_user["id"]))
    # create receipt mapping
    try:
        receipt_id = f"RCPT-{result.sale_date.date().isoformat().replace('-', '')}-{int(result.id):05d}"
    except Exception:
        receipt_id = f"RCPT-{int(result.id):05d}"
    rec = Receipt(receipt_id=receipt_id, sale_id=result.id)
    session.add(rec)
    await session.commit()
    await session.refresh(result)
    return {"receipt_id": receipt_id, "sale_id": result.id, "total_amount": result.total_amount, "status": "completed", "created_at": result.sale_date}


@router.get("/receipts/{receipt_id}/print")
async def print_receipt(receipt_id: str, session: AsyncSession = Depends(get_session), request: Request = None, current_user: dict = Depends(get_current_user)):
    # Look up receipt mapping
    res = await session.exec(select(Receipt).where(Receipt.receipt_id == receipt_id))
    mapping = res.first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    sale = await session.get(Sale, mapping.sale_id)
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    # Simple HTML receipt
    html = f"<html><body><h1>Receipt {receipt_id}</h1><p>Date: {sale.sale_date}</p><p>Total: {sale.total_amount}</p></body></html>"
    # Honor Accept header for pdf (best-effort)
    accept = request.headers.get("accept") if request else None
    if accept and "application/pdf" in accept:
        # We don't generate a real PDF here; return HTML with pdf content-type.
        return Response(content=html, media_type="application/pdf")
    return Response(content=html, media_type="text/html")


@router.post("/receipts/draft", response_model=dict)
async def save_receipt_draft(receipt: ReceiptCreate, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    # persist draft as JSON string in DraftReceipt table
    from app.model.models import DraftReceipt
    import uuid
    draft_id = f"DRAFT-{datetime.utcnow().date().isoformat().replace('-','')}-{uuid.uuid4().hex[:6].upper()}"
    dr = DraftReceipt(draft_id=draft_id, data=json.dumps(receipt.model_dump()), created_at=datetime.utcnow())
    from sqlalchemy.exc import ProgrammingError
    from sqlmodel import SQLModel
    from app.db.session import engine

    try:
        session.add(dr)
        await session.commit()
        await session.refresh(dr)
        return {"draft_id": dr.draft_id, "status": "draft"}
    except ProgrammingError as exc:
        # If the DraftReceipt table doesn't exist, create all metadata tables and retry once
        # Check MySQL error code 1146 (table doesn't exist) in the original exception when available
        orig = getattr(exc, "orig", None)
        code = None
        if orig is not None and hasattr(orig, "args") and orig.args:
            try:
                code = int(orig.args[0])
            except Exception:
                code = None
        if code == 1146 or "doesn't exist" in str(exc).lower():
            await session.rollback()
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
            # retry insert
            session.add(dr)
            await session.commit()
            await session.refresh(dr)
            return {"draft_id": dr.draft_id, "status": "draft"}
        # otherwise re-raise
        raise


@router.delete("/receipts/{receipt_id}")
async def cancel_receipt(receipt_id: str, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can cancel receipts")
    res = await session.exec(select(Receipt).where(Receipt.receipt_id == receipt_id))
    mapping = res.first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    # Use process_return to restock items
    sale = await session.get(Sale, mapping.sale_id)
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    # gather sale_item ids
    from app.model.models import SaleItem
    res_items = await session.exec(select(SaleItem).where(SaleItem.sale_id == sale.id))
    items = res_items.all()
    item_ids = [it.id for it in items]
    # call process_return synchronously
    await session.run_sync(lambda s: process_return(s, ReturnCreate(sale_id=sale.id, sale_item_ids=item_ids), current_user["id"]))
    # delete receipt mapping
    await session.delete(mapping)
    await session.commit()
    return {"message": f"Receipt {receipt_id} has been cancelled."}


@router.get("/payments/methods", response_model=list)
async def list_payment_methods():
    from app.model.models import PaymentMethod
    return [m.value for m in PaymentMethod]

@router.post("/returns", response_model=SaleResponse)
def process_return_endpoint(return_data: ReturnCreate, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can process returns"
        )
    return process_return(db, return_data, current_user.id)

@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale_endpoint(sale_id: int, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    return get_sale(db, sale_id)

@router.get("/", response_model=List[SaleResponse])
def get_all_sales_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    return get_all_sales(db, skip, limit)