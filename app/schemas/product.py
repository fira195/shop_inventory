# app/schemas/product.py
from pydantic import BaseModel
from typing import Optional
from app.model.models import ProductCondition, ProductStatus # Import Enums

# Shared properties
class ProductBase(BaseModel):
    name: str
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    description: Optional[str] = None
    condition: ProductCondition
    status: ProductStatus

# Properties to receive on item creation
class ProductCreate(ProductBase):
    pass # All fields from Base are required

# Properties to receive on item update
class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    description: Optional[str] = None
    condition: Optional[ProductCondition] = None
    status: Optional[ProductStatus] = None

# Properties shared by models stored in DB
class ProductInDBBase(ProductBase):
    id: int
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True #
        # This was orm_mode = True in Pydantic v1. 
        # It tells Pydantic to read data from ORM models (like SQLModel)

# Properties to return to client
class ProductRead(ProductInDBBase):
    pass

# You can create more complex schemas, e.g., for reading a product with its stock
# class ProductReadWithStock(ProductRead):
#     stock_items: list["StockItemRead"] = [] # Requires StockItemRead schema