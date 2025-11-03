from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List
from app.db.session import get_session
from app.auth.auth import get_current_user
from app.controller.stock_controller import create_stock_item, create_stock_movement, get_low_stock_alerts, transfer_stock
from app.schemas.stock import StockItemCreate, StockItemResponse, StockMovementCreate, StockMovementResponse, LowStockAlert, StockTransferCreate

router = APIRouter(prefix="/stock", tags=["Stock"])

@router.post("/items", response_model=StockItemResponse, status_code=status.HTTP_201_CREATED)
def create_stock_item_endpoint(stock_item: StockItemCreate, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create stock items"
        )
    return create_stock_item(db, stock_item, current_user.id)

@router.post("/movements", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED)
def create_stock_movement_endpoint(movement: StockMovementCreate, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create stock movements"
        )
    return create_stock_movement(db, movement, current_user.id)

@router.post("/transfers", response_model=StockItemResponse, status_code=status.HTTP_201_CREATED)
def transfer_stock_endpoint(transfer: StockTransferCreate, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can transfer stock"
        )
    return transfer_stock(db, transfer, current_user.id)

@router.get("/low-stock", response_model=List[LowStockAlert])
def get_low_stock_alerts_endpoint(threshold: int = 5, db: Session = Depends(get_session), current_user=Depends(get_current_user)):
    return get_low_stock_alerts(db, threshold)