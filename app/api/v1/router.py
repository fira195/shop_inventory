from fastapi import APIRouter
from app.api.v1.endpoints.product_router import router as product_router
from app.api.v1.endpoints.user_router import router as user_router
from app.api.v1.endpoints.sale_router import router as sale_router
from app.api.v1.endpoints.customer_router import router as customer_router
from app.api.v1.endpoints.repair_router import router as repair_router
from app.api.v1.endpoints.supplier_router import router as supplier_router
from app.api.v1.endpoints.stock_router import router as stock_router
from app.api.v1.endpoints.report_router import router as report_router
from app.api.v1.endpoints.branch_router import router as branch_router
from app.api.v1.endpoints.payment_router import router as payment_router
from app.api.v1.endpoints.inventory_router import router as inventory_router
from app.api.v1.endpoints.cash_ledger_router import router as cash_ledger_router
from app.api.v1.endpoints.customerbalance import router as customerbalance_router



router = APIRouter()

# Include all endpoint routers
router.include_router(product_router, tags=["Products"])
router.include_router(user_router, tags=["Users & Auth"])
router.include_router(sale_router, tags=["Sales"])
router.include_router(repair_router, tags=["Repairs"])
router.include_router(supplier_router, tags=["Suppliers"])
router.include_router(stock_router, tags=["Stock"])
router.include_router(customer_router, tags=["Customers"])
router.include_router(report_router, tags=["Reports"])
router.include_router(branch_router, tags=["Branches"])
router.include_router(inventory_router, tags=["Inventory"])
router.include_router(payment_router, tags=["Payments"])
router.include_router(cash_ledger_router, tags=["Finance"])
router.include_router(customerbalance_router, tags=["Customer Balance"])