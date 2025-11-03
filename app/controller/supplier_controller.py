from typing import List
from fastapi import HTTPException, status
from sqlmodel import Session, select
from sqlalchemy import func
from app.model.models import Supplier, PurchaseOrder, PurchaseOrderItem, POStatus, StockItem, StockMovement, MovementType, SourceType
from app.schemas.supplier import SupplierCreate, SupplierResponse, PurchaseOrderCreate, PurchaseOrderResponse, PurchaseOrderReceive
from datetime import datetime, timezone

def create_supplier(db: Session, supplier_data: SupplierCreate, current_user_id: int) -> SupplierResponse:
    supplier = Supplier(name=supplier_data.name)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)

def get_supplier(db: Session, supplier_id: int) -> SupplierResponse:
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    return SupplierResponse.model_validate(supplier)

def get_all_suppliers(db: Session, skip: int = 0, limit: int = 100) -> List[SupplierResponse]:
    suppliers = db.exec(select(Supplier).offset(skip).limit(limit)).all()
    return [SupplierResponse.model_validate(supplier) for supplier in suppliers]

def create_purchase_order(db: Session, po_data: PurchaseOrderCreate, current_user_id: int) -> PurchaseOrderResponse:
    purchase_order = PurchaseOrder(
        supplier_id=po_data.supplier_id,
        branch_id=po_data.branch_id,
        status=POStatus.planned,
        order_date=po_data.order_date,
        expected_arrival=po_data.expected_arrival,
        usd_rate_at_order=po_data.usd_rate_at_order,
        created_by=current_user_id,
        updated_by=current_user_id
    )
    db.add(purchase_order)
    db.flush()

    for item in po_data.items:
        po_item = PurchaseOrderItem(
            po_id=purchase_order.id,
            product_id=item.product_id,
            qty_ordered=item.qty_ordered,
            qty_received=0,
            unit_cost=item.unit_cost,
            notes=item.notes
        )
        db.add(po_item)

    db.commit()
    db.refresh(purchase_order)
    return PurchaseOrderResponse.model_validate(purchase_order)

def update_purchase_order_status(db: Session, po_id: int, status: POStatus, current_user_id: int) -> PurchaseOrderResponse:
    po = db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found"
        )
    po.status = status
    po.updated_by = current_user_id
    po.updated_at = datetime.now(timezone.utc)
    db.add(po)
    db.commit()
    db.refresh(po)
    return PurchaseOrderResponse.model_validate(po)

def receive_purchase_order(db: Session, receive_data: PurchaseOrderReceive, current_user_id: int) -> PurchaseOrderResponse:
    po = db.get(PurchaseOrder, receive_data.po_id)
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found"
        )
    if po.status not in [POStatus.planned, POStatus.ordered, POStatus.partially_received]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase order cannot be received in current status"
        )

    purchase_date = receive_data.purchase_date or datetime.now(timezone.utc).date()
    all_received = True

    for item_data in receive_data.items:
        po_item = db.get(PurchaseOrderItem, item_data.po_item_id)
        if not po_item or po_item.po_id != po.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase order item {item_data.po_item_id} not found or does not belong to PO"
            )
        if po_item.qty_received + item_data.qty_received > po_item.qty_ordered:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Received quantity exceeds ordered quantity for item {po_item.id}"
            )
        po_item.qty_received += item_data.qty_received
        if po_item.qty_received < po_item.qty_ordered:
            all_received = False
        db.add(po_item)

        sequence = db.exec(
            select(func.count(StockItem.id)).where(
                StockItem.product_id == po_item.product_id,
                StockItem.supplier_id == po.supplier_id
            )
        ).one() + 1
        sku = item_data.sku or f"PRODUCT-{po_item.product_id}-SUPPLIER-{po.supplier_id}-{sequence:04d}"
        serial_or_imei = item_data.serial_or_imei or f"IMEI-{po_item.product_id}-{purchase_date.year}-{sequence:04d}"

        if db.exec(select(StockItem).where(StockItem.sku == sku, StockItem.id != None)).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SKU {sku} already exists"
            )
        if db.exec(select(StockItem).where(StockItem.serial_or_imei == serial_or_imei, StockItem.id != None)).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Serial/IMEI {serial_or_imei} already exists"
            )

        stock_item = db.exec(
            select(StockItem).where(
                StockItem.product_id == po_item.product_id,
                StockItem.sku == sku,
                StockItem.serial_or_imei == serial_or_imei,
                StockItem.location == receive_data.location,
                StockItem.supplier_id == po.supplier_id
            )
        ).first()
        if stock_item:
            stock_item.qty_on_hand += item_data.qty_received
            stock_item.updated_by = current_user_id
            stock_item.updated_at = datetime.now(timezone.utc)
            stock_item.status = "available"
        else:
            stock_item = StockItem(
                product_id=po_item.product_id,
                sku=sku,
                serial_or_imei=serial_or_imei,
                qty_on_hand=item_data.qty_received,
                location=receive_data.location,
                status="available",
                supplier_id=po.supplier_id,
                source_type=SourceType.formal,
                invoice_no=receive_data.invoice_no,
                purchase_date=purchase_date,
                cost_price=po_item.unit_cost,
                usd_rate_at_purchase=po.usd_rate_at_order,
                created_by=current_user_id,
                updated_by=current_user_id
            )
        db.add(stock_item)
        db.flush()

        stock_movement = StockMovement(
            stock_item_id=stock_item.id,
            movement_type=MovementType.IN,
            quantity=item_data.qty_received,
            reference=f"PO {po.id} receipt",
            reason=f"Received for PO {po.id}",
            performed_by=current_user_id
        )
        db.add(stock_movement)

    po.status = POStatus.received if all_received else POStatus.partially_received
    po.updated_by = current_user_id
    po.updated_at = datetime.now(timezone.utc)
    db.add(po)

    db.commit()
    db.refresh(po)
    return PurchaseOrderResponse.model_validate(po)