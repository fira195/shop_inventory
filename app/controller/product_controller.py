from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException
from app.model.models import Product
from app.schemas.product import ProductCreate, ProductUpdate # Import schemas

# Create Product
async def create_product(session: AsyncSession, product_data: ProductCreate):
    # Convert Pydantic schema to a dictionary, then to SQLModel instance
    # Pass created_by_id if you add it to the function signature
    product_dict = product_data.model_dump()
    product = Product(**product_dict) 
    
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product

# Get all products
async def get_products(session: AsyncSession):
    result = await session.exec(select(Product))
    return result.all()

# Get single product by ID
async def get_product(session: AsyncSession, product_id: int):
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# Update Product
async def update_product(
    session: AsyncSession, product_id: int, product_data: ProductUpdate
):
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get data as a dict, excluding any fields that were not set (unset)
    # This prevents accidentally overwriting fields with None
    update_data = product_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(product, key, value)
        
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product

# Delete Product
async def delete_product(session: AsyncSession, product_id: int):
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await session.delete(product)
    await session.commit()
    # Don't return a body for a 204 response
    return