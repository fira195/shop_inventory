from typing import Optional
from pydantic import BaseModel
from enum import Enum
from datetime import datetime, date


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    CUSTOMER = "customer"
    STAFF = "staff"

class UserBase(BaseModel):
    # Make username optional in the public schema
    username: Optional[str] = None


class UserResponse(UserBase):
    id: int
    role: UserRole

    class Config:
        from_attributes = True