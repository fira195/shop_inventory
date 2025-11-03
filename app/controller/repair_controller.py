from typing import List
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.model.models import Repair, RepairItem, StockItem, RepairStatus
from app.schemas.repair import RepairCreate, RepairResponse, RepairItemCreate
from datetime import datetime, timezone

def create_repair(db: Session, repair_data: RepairCreate, current_user_id: int) -> RepairResponse:
    # Validate stock availability for parts
    for item in repair_data.items:
        stock = db.get(StockItem, item.product_id)
        if not stock or stock.qty_on_hand < item.qty_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for product {item.product_id}"
            )

    # Create Repair
    repair = Repair(
        customer_id=repair_data.customer_id,
        device_description=repair_data.device_description,
        deposit_amount=repair_data.deposit_amount,
        status=RepairStatus.received,
        assigned_technician_id=repair_data.assigned_technician_id,
        received_date=datetime.now(timezone.utc),
        due_date=repair_data.due_date,
        notes=repair_data.notes
    )
    db.add(repair)
    db.flush()

    # Create RepairItems and update StockItems
    for item in repair_data.items:
        stock = db.get(StockItem, item.product_id)
        repair_item = RepairItem(
            repair_id=repair.id,
            product_id=item.product_id,
            qty_used=item.qty_used,
            unit_cost=item.unit_cost,
            unit_sale_price=item.unit_sale_price
        )
        stock.qty_on_hand -= item.qty_used
        stock.status = "sold" if stock.qty_on_hand == 0 else stock.status
        db.add(repair_item)
        db.add(stock)

    db.commit()
    db.refresh(repair)
    return RepairResponse.model_validate(repair)

def update_repair_status(db: Session, repair_id: int, status: RepairStatus, current_user_id: int) -> RepairResponse:
    repair = db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repair not found"
        )
    repair.status = status
    if status == RepairStatus.completed:
        repair.completion_date = datetime.now(timezone.utc)
    repair.updated_by = current_user_id
    db.add(repair)
    db.commit()
    db.refresh(repair)
    return RepairResponse.model_validate(repair)

def get_repair(db: Session, repair_id: int) -> RepairResponse:
    repair = db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repair not found"
        )
    return RepairResponse.model_validate(repair)

def get_all_repairs(db: Session, skip: int = 0, limit: int = 100) -> List[RepairResponse]:
    repairs = db.exec(select(Repair).offset(skip).limit(limit)).all()
    return [RepairResponse.model_validate(repair) for repair in repairs]