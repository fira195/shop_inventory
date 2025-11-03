from typing import List
from fastapi import HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from app.model.models import StockItem, StockMovement, MovementType, Product, Supplier
from app.schemas.stock import StockItemCreate, StockItemResponse, StockMovementCreate, StockMovementResponse, LowStockAlert, StockTransferCreate
from datetime import datetime, timezone

def create_stock_item(db: Session, stock_item_data: StockItemCreate, current_user_id: int) -> StockItemResponse:
    # validate foreign keys early to provide a clear 400 response instead of a 500 IntegrityError
    product = db.get(Product, stock_item_data.product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"product_id {stock_item_data.product_id} does not reference an existing product"
        )
    if stock_item_data.supplier_id:
        supplier = db.get(Supplier, stock_item_data.supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"supplier_id {stock_item_data.supplier_id} does not reference an existing supplier"
            )

    stock_item = StockItem(
        product_id=stock_item_data.product_id,
        sku=stock_item_data.sku,
        serial_or_imei=stock_item_data.serial_or_imei,
        warranty_period=stock_item_data.warranty_period,
        qty_on_hand=stock_item_data.qty_on_hand,
        location=stock_item_data.location,
        status=stock_item_data.status,
        supplier_id=stock_item_data.supplier_id,
        source_type=stock_item_data.source_type,
        invoice_no=stock_item_data.invoice_no,
        purchase_date=stock_item_data.purchase_date,
        cost_price=stock_item_data.cost_price,
        landed_cost=stock_item_data.landed_cost,
        sale_price=stock_item_data.sale_price,
        usd_rate_at_purchase=stock_item_data.usd_rate_at_purchase,
        margin=stock_item_data.sale_price - stock_item_data.cost_price if stock_item_data.sale_price and stock_item_data.cost_price else None,
        notes=stock_item_data.notes,
        created_by=current_user_id,
        updated_by=current_user_id,
        version=1
    )
    db.add(stock_item)
    try:
        db.commit()
    except SAIntegrityError as e:
        db.rollback()
        # Provide a clear 400 with the DB error message (safe; does not leak secrets)
        detail = str(getattr(e, 'orig', e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database integrity error: {detail}")
    db.flush()

    stock_movement = StockMovement(
        stock_item_id=stock_item.id,
        movement_type=MovementType.IN,
        quantity=stock_item_data.qty_on_hand,
        reference=f"Initial stock creation for SKU {stock_item.sku}",
        performed_by=current_user_id
    )
    db.add(stock_movement)
    try:
        db.commit()
    except SAIntegrityError as e:
        db.rollback()
        detail = str(getattr(e, 'orig', e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database integrity error: {detail}")

    return StockItemResponse.model_validate(stock_item)

def create_stock_movement(db: Session, movement_data: StockMovementCreate, current_user_id: int) -> StockMovementResponse:
    stock_item = db.get(StockItem, movement_data.stock_item_id)
    if not stock_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock item not found"
        )
    
    if movement_data.movement_type == MovementType.OUT and stock_item.qty_on_hand < movement_data.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient stock quantity"
        )
    
    stock_movement = StockMovement(
        stock_item_id=movement_data.stock_item_id,
        movement_type=movement_data.movement_type,
        quantity=movement_data.quantity,
        reference=movement_data.reference,
        reason=movement_data.reason,
        performed_by=current_user_id
    )
    
    current_version = stock_item.version
    if movement_data.movement_type == MovementType.IN:
        stock_item.qty_on_hand += movement_data.quantity
    elif movement_data.movement_type == MovementType.OUT:
        stock_item.qty_on_hand -= movement_data.quantity
    elif movement_data.movement_type == MovementType.ADJUSTMENT:
        stock_item.qty_on_hand = movement_data.quantity
    elif movement_data.movement_type == MovementType.RETURN:
        stock_item.qty_on_hand += movement_data.quantity
        stock_item.status = "returned"
    
    stock_item.updated_by = current_user_id
    stock_item.updated_at = datetime.now(timezone.utc)
    stock_item.version += 1
    
    db.add(stock_movement)
    db.add(stock_item)
    
    try:
        db.commit()
    except Exception:
        db.rollback()
        if db.get(StockItem, movement_data.stock_item_id).version != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent update detected, please retry"
            )
        raise
    
    db.refresh(stock_movement)
    return StockMovementResponse.model_validate(stock_movement)

def transfer_stock(db: Session, transfer_data: StockTransferCreate, current_user_id: int) -> StockItemResponse:
    source_stock = db.get(StockItem, transfer_data.stock_item_id)
    if not source_stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source stock item not found"
        )
    if source_stock.qty_on_hand < transfer_data.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient stock quantity at source location"
        )
    if source_stock.location != transfer_data.from_location:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source stock item location does not match from_location"
        )
    if transfer_data.from_location == transfer_data.to_location:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination locations cannot be the same"
        )

    source_version = source_stock.version
    dest_stock = db.exec(
        select(StockItem).where(
            StockItem.product_id == source_stock.product_id,
            StockItem.sku == source_stock.sku,
            StockItem.serial_or_imei == source_stock.serial_or_imei,
            StockItem.location == transfer_data.to_location
        )
    ).first()

    source_stock.qty_on_hand -= transfer_data.quantity
    source_stock.updated_by = current_user_id
    source_stock.updated_at = datetime.now(timezone.utc)
    source_stock.version += 1
    if source_stock.qty_on_hand == 0:
        source_stock.status = "sold"

    if dest_stock:
        dest_version = dest_stock.version
        dest_stock.qty_on_hand += transfer_data.quantity
        dest_stock.updated_by = current_user_id
        dest_stock.updated_at = datetime.now(timezone.utc)
        dest_stock.version += 1
        dest_stock.status = "available"
        db.add(dest_stock)
    else:
        dest_stock = StockItem(
            product_id=source_stock.product_id,
            sku=source_stock.sku,
            serial_or_imei=source_stock.serial_or_imei,
            warranty_period=source_stock.warranty_period,
            qty_on_hand=transfer_data.quantity,
            location=transfer_data.to_location,
            status="available",
            supplier_id=source_stock.supplier_id,
            source_type=source_stock.source_type,
            invoice_no=source_stock.invoice_no,
            purchase_date=source_stock.purchase_date,
            cost_price=source_stock.cost_price,
            landed_cost=source_stock.landed_cost,
            sale_price=source_stock.sale_price,
            usd_rate_at_purchase=source_stock.usd_rate_at_purchase,
            margin=source_stock.margin,
            notes=source_stock.notes,
            created_by=current_user_id,
            updated_by=current_user_id,
            version=1
        )
        db.add(dest_stock)

    source_movement = StockMovement(
        stock_item_id=source_stock.id,
        movement_type=MovementType.OUT,
        quantity=transfer_data.quantity,
        reference=transfer_data.reference or f"Transfer to {transfer_data.to_location}",
        reason=transfer_data.reason or f"Transfer from {transfer_data.from_location} to {transfer_data.to_location}",
        performed_by=current_user_id
    )
    dest_movement = StockMovement(
        stock_item_id=dest_stock.id if dest_stock.id else None,
        movement_type=MovementType.IN,
        quantity=transfer_data.quantity,
        reference=transfer_data.reference or f"Transfer from {transfer_data.from_location}",
        reason=transfer_data.reason or f"Transfer from {transfer_data.from_location} to {transfer_data.to_location}",
        performed_by=current_user_id
    )

    db.add(source_stock)
    db.add(source_movement)
    db.add(dest_movement)
    db.flush()
    if not dest_movement.stock_item_id:
        dest_movement.stock_item_id = dest_stock.id
        db.add(dest_movement)

    try:
        db.commit()
    except Exception:
        db.rollback()
        if db.get(StockItem, transfer_data.stock_item_id).version != source_version or (dest_stock and db.get(StockItem, dest_stock.id).version != dest_version):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent update detected, please retry"
            )
        raise
    
    db.refresh(dest_stock)
    return StockItemResponse.model_validate(dest_stock)

def get_low_stock_alerts(db: Session, threshold: int = 5) -> List[LowStockAlert]:
    stock_items = db.exec(
        select(StockItem).where(StockItem.qty_on_hand < threshold, StockItem.status == "available")
    ).all()
    return [LowStockAlert(
        stock_item_id=item.id,
        sku=item.sku,
        product_id=item.product_id,
        qty_on_hand=item.qty_on_hand
    ) for item in stock_items]