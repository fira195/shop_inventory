from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import get_session
from app.model.models import User, UserCreate, UserRead
from app.config.config import settings
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import timedelta, datetime
from fastapi.security import OAuth2PasswordRequestForm
from typing import Optional, List
import os
import re

router = APIRouter(prefix="/users", tags=["Users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALLOWED_ROLES = {"staff", "customer"}  # Allow staff and customer for public registration
ALLOW_DEV_REGISTRATION = os.getenv("ALLOW_DEV_REGISTRATION", "true").lower() == "true"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire, "role": data.get("role", "unknown")})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)):
    # Try to decode token using configured SECRET_KEY. If that fails, try the legacy
    # env JWT_SECRET for compatibility with older tokens.
    last_exc = None
    for secret in (getattr(settings, "SECRET_KEY", None), os.getenv("JWT_SECRET", None)):
        if not secret:
            continue
        try:
            payload = jwt.decode(token, secret, algorithms=[getattr(settings, "ALGORITHM", "HS256")])
            # If we decoded successfully, break out
            break
        except JWTError as exc:
            last_exc = exc
            payload = None
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Payload may contain 'sub' as either user id or username, and may or may not include role.
    sub = payload.get("sub")
    role = payload.get("role")
    user = None

    # Try to interpret sub as an integer id first
    if sub is not None:
        try:
            uid = int(sub)
            user = (await session.exec(select(User).where(User.id == uid))).first()
            if user and not role:
                role = user.role
        except Exception:
            # treat sub as username
            user = (await session.exec(select(User).where(User.username == str(sub)))).first()
            if user and not role:
                role = user.role

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user or role")

    if not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token (missing role)")

    if user.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user or role")

    return {"id": int(user.id), "role": role}

def validate_email(email: str) -> bool:
    """Validate email format."""
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(email_pattern, email))

def validate_phone(phone: Optional[str]) -> bool:
    """Validate phone number format (if provided)."""
    if phone is None:
        return True
    phone_pattern = r"^\+?\d{10,15}$"
    return bool(re.match(phone_pattern, phone))

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, session: AsyncSession = Depends(get_session)):
    if user.role.lower() not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only staff or customer roles can be registered"
        )
    if not validate_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    if user.role.lower() == "customer" and not user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required for customers"
        )
    if user.role.lower() == "customer" and not user.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required for customers"
        )
    if user.phone and not validate_phone(user.phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )
    # For customers username is optional; if provided it must be unique.
    existing_user = None
    if user.username:
        existing_user = (await session.exec(select(User).where(User.username == user.username))).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    existing_email = (await session.exec(select(User).where(User.email == user.email))).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    if user.phone:
        existing_phone = (await session.exec(select(User).where(User.phone == user.phone))).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
    hashed_password = pwd_context.hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        phone=user.phone,
        name=user.name,
        hashed_password=hashed_password,
        role=user.role,
        created_by=None,
        updated_by=None
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    access_token = create_access_token({"sub": str(db_user.id), "role": db_user.role})
    return {
        **db_user.dict(),
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/dev-register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def dev_register_admin(user: UserCreate, session: AsyncSession = Depends(get_session)):
    if not ALLOW_DEV_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Development registration disabled"
        )
    if user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint can only create admin users"
        )
    if not validate_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    if user.phone and not validate_phone(user.phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )
    existing_user = None
    if user.username:
        existing_user = (await session.exec(select(User).where(User.username == user.username))).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    existing_email = (await session.exec(select(User).where(User.email == user.email))).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    if user.phone:
        existing_phone = (await session.exec(select(User).where(User.phone == user.phone))).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
    hashed_password = pwd_context.hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        phone=user.phone,
        name=user.name,
        hashed_password=hashed_password,
        role=user.role,
        created_by=None,
        updated_by=None
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    access_token = create_access_token({"sub": str(db_user.id), "role": db_user.role})
    print(f"⚠️ DEVELOPMENT: Admin user '{user.username}' created!")
    return {
        **db_user.dict(),
        "access_token": access_token,
        "token_type": "bearer",
        "warning": "This is a development endpoint. Disable in production!"
    }

@router.post("/login", response_model=dict)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_session)):
    user = (await session.exec(select(User).where(User.username == form_data.username))).first()
    if user and pwd_context.verify(form_data.password, user.hashed_password):
        access_token = create_access_token({"sub": str(user.id), "role": user.role})
        refresh_token = create_access_token({"sub": str(user.id), "role": user.role}, timedelta(days=7))
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "role": user.role
        }
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create users"
        )
    if not validate_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    if user.role.lower() == "customer" and not user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required for customers"
        )
    if user.role.lower() == "customer" and not user.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required for customers"
        )
    if user.phone and not validate_phone(user.phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )
    # username is optional for customers; check uniqueness only if provided
    existing_user = None
    if user.username:
        existing_user = (await session.exec(select(User).where(User.username == user.username))).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    existing_email = (await session.exec(select(User).where(User.email == user.email))).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    if user.phone:
        existing_phone = (await session.exec(select(User).where(User.phone == user.phone))).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
    hashed_password = pwd_context.hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        phone=user.phone,
        name=user.name,
        hashed_password=hashed_password,
        role=user.role,
        created_by=current_user["id"],
        updated_by=current_user["id"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


@router.get("/", response_model=List[UserRead])
async def get_all_users(session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    """Return all users (admin only)."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list users"
        )
    users = (await session.exec(select(User))).all()
    return users
