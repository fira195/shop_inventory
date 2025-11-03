from typing import List
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.model.models import Customer, Sale, Repair
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse

def create_customer(db: Session, customer_data: CustomerCreate, current_user_id: int) -> CustomerResponse:
    customer = Customer(
        name=customer_data.name,
        phone=customer_data.phone
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerResponse.from_orm(customer)

def get_customer(db: Session, customer_id: int) -> CustomerResponse:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    return CustomerResponse.from_orm(customer)

def get_all_customers(db: Session, skip: int = 0, limit: int = 100) -> List[CustomerResponse]:
    customers = db.exec(select(Customer).offset(skip).limit(limit)).all()
    return [CustomerResponse.from_orm(customer) for customer in customers]

def update_customer(db: Session, customer_id: int, customer_data: CustomerUpdate, current_user_id: int) -> CustomerResponse:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    update_data = customer_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(customer, key, value)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerResponse.from_orm(customer)

def delete_customer(db: Session, customer_id: int, current_user_id: int) -> dict:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    if db.exec(select(Sale).where(Sale.customer_id == customer_id)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete customer with active sales"
        )
    if db.exec(select(Repair).where(Repair.customer_id == customer_id)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete customer with active repairs"
        )
    db.delete(customer)
    db.commit()
    return {"detail": "Customer deleted successfully"}