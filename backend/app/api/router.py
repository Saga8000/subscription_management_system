from fastapi import APIRouter

from app.api.v1 import (
    auth,
    customers,
    discounts,
    invoices,
    payments,
    plans,
    products,
    quotations,
    reports,
    subscriptions,
    users,
)

api_router = APIRouter(prefix="/api/v1")
for module in (
    auth, users, customers, products, plans, quotations,
    subscriptions, invoices, payments, discounts, reports,
):
    api_router.include_router(module.router)
