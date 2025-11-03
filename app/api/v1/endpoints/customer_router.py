from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.db.session import get_session
from app.schemas.customer import CustomerCreate, CustomerRead
from app.model.models import User
from app.api.v1.endpoints.user_router import get_current_user
from passlib.context import CryptContext
from datetime import datetime
import secrets

router = APIRouter(prefix="/customers", tags=["Customers"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/", response_model=list[CustomerRead])
async def list_customers(session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
	if current_user.get("role") != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can list customers")
	results = await session.exec(select(User).where(User.role == "customer"))
	users = results.all()
	out = []
	for u in users:
		out.append(CustomerRead(id=u.id, name=u.name or "", phone=u.phone or "", created_at=u.created_at, updated_at=u.updated_at))
	return out


@router.post("/", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(customer: CustomerCreate, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
	if current_user.get("role") not in ("admin", "manager"):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or managers can create customers")
	existing = await session.exec(select(User).where((User.email == customer.email) | (User.phone == customer.phone)))
	if existing.first():
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer with given email or phone already exists")
	temp_password = secrets.token_urlsafe(8)
	hashed = pwd_context.hash(temp_password)
	db_user = User(
		username=None,
		email=customer.email,
		phone=customer.phone,
		name=customer.name,
		hashed_password=hashed,
		role="customer",
		created_by=current_user.get("id"),
		updated_by=current_user.get("id"),
		created_at=datetime.utcnow(),
		updated_at=datetime.utcnow()
	)
	session.add(db_user)
	await session.commit()
	await session.refresh(db_user)
	return CustomerRead(id=db_user.id, name=db_user.name or "", phone=db_user.phone or "", created_at=db_user.created_at, updated_at=db_user.updated_at)