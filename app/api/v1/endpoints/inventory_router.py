from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from app.db.session import get_session
from app.api.v1.endpoints.user_router import get_current_user
from app.model.models import Product, StockItem, StockMovement
from app.schemas.stock import StockItemCreate, StockTransferCreate
from app.controller.stock_controller import get_low_stock_alerts, transfer_stock

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/", response_model=list)
async def get_inventory(page: int = 1, limit: int = 100, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    # return aggregated inventory per product per branch
    if current_user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or managers can view inventory")

    query = (
        select(
            Product.id.label("id"),
            Product.name.label("name"),
            StockItem.sku.label("sku"),
            StockItem.location.label("branch"),
            func.coalesce(func.sum(StockItem.qty_on_hand), 0).label("quantity"),
            StockItem.status.label("status"),
            func.max(StockItem.updated_at).label("last_updated")
        )
        .join(StockItem, StockItem.product_id == Product.id)
        .group_by(Product.id, Product.name, StockItem.sku, StockItem.location, StockItem.status)
        .order_by(Product.name)
    )
    offset = (max(page, 1) - 1) * max(limit, 1)
    res = await session.exec(query.offset(offset).limit(limit))
    rows = res.all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "name": r.name,
            "sku": r.sku,
            "branch": r.branch,
            "quantity": int(r.quantity or 0),
            "status": r.status,
            "last_updated": r.last_updated.date().isoformat() if r.last_updated else None
        })
    return out


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_stock(item: StockItemCreate, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or managers can add stock")
    # delegate to controller (sync) via run_sync
    from app.controller.stock_controller import create_stock_item
    result = await session.run_sync(lambda s: create_stock_item(s, item, current_user.get("id")))
    return {"id": result.id, "message": "Stock added successfully", "product_name": result.product.name if getattr(result, 'product', None) else None, "branch": result.location, "quantity": result.qty_on_hand, "status": result.status}


@router.get("/search", response_model=list)
async def search_inventory(query: Optional[str] = None, branch: Optional[str] = None, status: Optional[str] = None, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or managers can search inventory")
    q = select(Product.id.label("id"), Product.name.label("name"), StockItem.sku.label("sku"), StockItem.location.label("branch"), StockItem.qty_on_hand.label("quantity"), StockItem.status.label("status"))
    q = q.join(StockItem, StockItem.product_id == Product.id)
    if query:
        q = q.where((Product.name.ilike(f"%{query}%")) | (StockItem.sku.ilike(f"%{query}%")))
    if branch:
        q = q.where(StockItem.location == branch)
    if status:
        q = q.where(StockItem.status == status)
    res = await session.exec(q.order_by(Product.name))
    rows = res.all()
    out = []
    for r in rows:
        out.append({"id": r.id, "name": r.name, "sku": r.sku, "branch": r.branch, "quantity": int(r.quantity or 0), "status": r.status})
    return out


@router.get("/alerts/low-stock", response_model=list)
async def low_stock_alerts(threshold: int = 5, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or managers can view low stock alerts")
    # run sync controller
    result = await session.run_sync(lambda s: get_low_stock_alerts(s, threshold))
    out = []
    for it in result:
        # map to UI-friendly structure
        out.append({"product_name": None, "branch": None, "quantity": it.qty_on_hand, "threshold": threshold})
    return out


@router.post("/transfer", response_model=dict)
async def transfer_inventory(transfer: StockTransferCreate, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or managers can transfer stock")
    # delegate to controller
    result = await session.run_sync(lambda s: transfer_stock(s, transfer, current_user.get("id")))
    return {"message": f"Transferred {transfer.quantity} units of SKU {result.sku} to {transfer.to_location}."}


@router.patch("/adjust/{product_id}")
async def adjust_stock(product_id: int, adjustment: dict, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    # adjustment: {adjustment_type: increase|decrease|set, quantity: int, reason: str, branch: Optional[str]}
    if current_user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or managers can adjust stock")
    adj_type = adjustment.get("adjustment_type")
    qty = int(adjustment.get("quantity", 0))
    reason = adjustment.get("reason")
    branch = adjustment.get("branch")
    # choose a stock item for product and branch
    q = select(StockItem).where(StockItem.product_id == product_id)
    if branch:
        q = q.where(StockItem.location == branch)
    res = await session.exec(q)
    stock = res.first()
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock item not found for product/branch")
    # use stock movement controller
    from app.controller.stock_controller import create_stock_movement
    from app.schemas.stock import StockMovementCreate
    if adj_type == "increase":
        mv = StockMovementCreate(stock_item_id=stock.id, movement_type="IN", quantity=qty, reference=reason, reason=reason)
    elif adj_type == "decrease":
        mv = StockMovementCreate(stock_item_id=stock.id, movement_type="OUT", quantity=qty, reference=reason, reason=reason)
    elif adj_type == "set":
        mv = StockMovementCreate(stock_item_id=stock.id, movement_type="ADJUSTMENT", quantity=qty, reference=reason, reason=reason)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid adjustment_type")
    result = await session.run_sync(lambda s: create_stock_movement(s, mv, current_user.get("id")))
    return {"message": f"Stock for product ID {product_id} updated.", "new_quantity": result.qty_on_hand}


@router.get("/history/{product_id}", response_model=list)
async def inventory_history(product_id: int, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or managers can view history")
    q = select(StockMovement, StockItem).join(StockItem, StockMovement.stock_item_id == StockItem.id).where(StockItem.product_id == product_id).order_by(StockMovement.created_at.desc())
    res = await session.exec(q)
    rows = res.all()
    out = []
    for mv, si in rows:
        out.append({"action": mv.movement_type, "quantity": mv.quantity, "user": mv.performed_by, "timestamp": mv.created_at.isoformat()})
    return out
