from fastapi import APIRouter
from app.model.models import PaymentMethod

router = APIRouter(prefix="/payments", tags=["Payments"]) 

@router.get("/methods", response_model=list)
async def list_payment_methods():
    return [m.value for m in PaymentMethod]
