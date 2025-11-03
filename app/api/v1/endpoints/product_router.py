from fastapi import APIRouter, Depends, HTTPException, status
from app.db.session import get_session
from sqlmodel import select
from app.model.models import Product
from app.model.models import Category, Brand

from sqlmodel.ext.asyncio.session import AsyncSession
from app.controller import product_controller as controller
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.model.models import User # To get user type hinting
from app.api.v1.endpoints.user_router import get_current_user # use the async auth dependency used by the app endpoints
from datetime import datetime

# The prefix is defined here for modularity
router = APIRouter(prefix="/products")

# Create Product
@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or managers can create products"
        )
    existing_product = (await session.exec(select(Product).where(Product.name == product.name))).first()
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product name already exists"
        )
    # Map all incoming fields to the Product model so required columns are populated
    db_product = Product(
        name=product.name,
        category_id=product.category_id,
        brand_id=product.brand_id,
        description=product.description,
        condition=product.condition,
        status=product.status,
        created_by=current_user["id"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_product)
    await session.commit()
    await session.refresh(db_product)
    return db_product

# Get all products
@router.get("/", response_model=list[ProductRead])
async def get_products_route(session: AsyncSession = Depends(get_session)):
    return await controller.get_products(session)


@router.get("/categories", response_model=list[dict])
async def get_categories_route(session: AsyncSession = Depends(get_session)):
    # return list of categories as {id, name}
    results = await session.exec(select(Category))
    cats = results.all()
    return [{"id": c.id, "name": c.name} for c in cats]


@router.get("/brands", response_model=list[dict])
async def get_brands_route(session: AsyncSession = Depends(get_session)):
    results = await session.exec(select(Brand))
    brands = results.all()
    return [{"id": b.id, "name": b.name} for b in brands]


@router.get("/dropdown", response_model=list[dict])
async def get_products_dropdown(session: AsyncSession = Depends(get_session)):
    # return id, name, unit_price (max sale_price) and total stock
    from sqlmodel import select, func
    from app.model.models import StockItem

    query = (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            func.coalesce(func.max(StockItem.sale_price), 0).label("unit_price"),
            func.coalesce(func.sum(StockItem.qty_on_hand), 0).label("stock")
        )
        .join(StockItem, StockItem.product_id == Product.id, isouter=True)
        .group_by(Product.id, Product.name)
    )
    res = await session.exec(query)
    items = []
    for r in res.all():
        items.append({"id": r.product_id, "name": r.product_name, "unit_price": float(r.unit_price or 0.0), "stock": int(r.stock or 0)})
    return items


@router.get("/search", response_model=list[dict])
async def search_products(
    query: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """Search products by name/model, and optionally filter by category, brand and status.

    Example: /products/search?query=iphone&category=Smartphones&status=Active
    """
    from sqlmodel import select
    stmt = (
        select(
            Product.id.label("id"),
            Category.name.label("category"),
            Brand.name.label("brand"),
            Product.name.label("model"),
            Product.status.label("status"),
        )
        .join(Category, Category.id == Product.category_id, isouter=True)
        .join(Brand, Brand.id == Product.brand_id, isouter=True)
    )

    if query:
        stmt = stmt.where(Product.name.ilike(f"%{query}%"))
    if category:
        stmt = stmt.where(Category.name.ilike(category))
    if brand:
        stmt = stmt.where(Brand.name.ilike(brand))
    if status:
        stmt = stmt.where(Product.status.ilike(status))

    res = await session.exec(stmt)
    rows = res.all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "category": r.category,
            "brand": r.brand,
            "model": r.model,
            "status": r.status
        })
    return out


@router.get("/low-stock", response_model=list[dict])
async def products_low_stock(threshold: int = 5, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    """Return products that are below the given stock threshold."""
    from app.controller.report_controller import get_stock_status
    # run sync controller
    status = await session.run_sync(lambda s: get_stock_status(s, threshold))
    items = []
    for it in status.items:
        if it.is_low_stock:
            items.append({
                "product_name": it.product_name,
                "sku": it.sku,
                "current_stock": it.qty_on_hand,
                "reorder_level": threshold
            })
    return items

# Get single product by ID
@router.get("/{product_id}", response_model=ProductRead)
async def get_product_route(
    product_id: int, 
    session: AsyncSession = Depends(get_session)
):
    return await controller.get_product(session, product_id)

# Update Product
@router.put("/{product_id}", response_model=ProductRead)
async def update_product_route(
    product_id: int,
    product: ProductUpdate, # Use Pydantic schema
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user) # Protect
):
    return await controller.update_product(session, product_id, product)

# Delete Product
@router.delete("/{product_id}", status_code=204) # 204 No Content is standard
async def delete_product_route(
    product_id: int, 
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user) # Protect
):
    await controller.delete_product(session, product_id)
    return {"detail": "Product deleted"} # Note: 204 responses shouldn't have a body