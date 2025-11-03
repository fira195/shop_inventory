from typing import List
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.model.models import User
from app.schemas.user import UserResponse
from app.model.models import UserCreate
from passlib.context import CryptContext
from datetime import datetime, timezone

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_user(db: Session, user_data: UserCreate, current_user_id: int) -> UserResponse:
    if db.exec(select(User).where(User.username == user_data.username)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    hashed_password = pwd_context.hash(user_data.password)
    user = User(
        username=user_data.username,
        password=hashed_password,
        role=user_data.role,
        created_by=current_user_id,
        updated_by=current_user_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)

def get_user(db: Session, user_id: int) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.model_validate(user)

def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[UserResponse]:
    users = db.exec(select(User).offset(skip).limit(limit)).all()
    return [UserResponse.model_validate(user) for user in users]

def update_user(db: Session, user_id: int, user_data: UserCreate, current_user_id: int) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if user_data.username != user.username and db.exec(select(User).where(User.username == user_data.username)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    user.username = user_data.username
    if user_data.password:
        user.password = pwd_context.hash(user_data.password)
    user.role = user_data.role
    user.updated_by = current_user_id
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)

def delete_user(db: Session, user_id: int, current_user_id: int) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if user.id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete own user account"
        )
    db.delete(user)
    db.commit()
    return {"detail": "User deleted successfully"}