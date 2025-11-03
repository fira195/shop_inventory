from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List
from sqlmodel import select
from app.db.session import get_session
from app.api.v1.endpoints.user_router import get_current_user
from app.schemas.supplier import SupplierCreate, SupplierResponse
from app.schemas.user import UserRole
from app.model.models import Supplier

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(supplier: SupplierCreate, db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create suppliers")
    db_supplier = Supplier(name=supplier.name)
    db.add(db_supplier)
    await db.commit()
    await db.refresh(db_supplier)
    return db_supplier


@router.get("/", response_model=List[SupplierResponse])
async def list_suppliers(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view suppliers")
    res = await db.exec(select(Supplier).offset(skip).limit(limit))
    suppliers = res.all()
    return suppliers


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(supplier_id: int, db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view supplier details")
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(supplier_id: int, payload: SupplierCreate, db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can update suppliers")
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    supplier.name = payload.name
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: int, db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete suppliers")
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    await db.delete(supplier)
    await db.commit()
    return {"detail": "Supplier deleted"}