from fastapi import APIRouter

from app.api import (
    admin,
    approvals,
    auth,
    billing,
    customers,
    dashboard,
    fulfillment,
    negotiations,
    notifications,
    products,
    quotes,
    reports,
    search,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(negotiations.router, prefix="/negotiations", tags=["negotiations"])
api_router.include_router(billing.router, tags=["billing"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(fulfillment.router, tags=["fulfillment"])
