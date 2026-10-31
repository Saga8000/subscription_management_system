"""Loads demo data through the public API so every record passes the same validation as the UI.

Usage (from backend/):  python -m app.seed
Refuses to run if any user already exists, so it never mixes demo data into a used database.
"""

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import hash_password
from app.database import SessionLocal
from app.main import app
from app.models import User
from app.models.enums import UserRole

DEMO_USERS = {
    "admin": ("admin@brightloop-demo.com", "Admin@Demo2026"),
    "staff": ("staff@brightloop-demo.com", "Staff@Demo2026"),
    "customer": ("ananya@acme-demo.com", "Customer@Demo2026"),
}


def _ok(response: Any) -> Any:
    if response.status_code >= 400:
        raise RuntimeError(f"{response.request.method} {response.request.url} -> {response.status_code}: {response.text}")
    return response.json()


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            print("Users already exist; seed skipped (it only runs on an empty database).")
            return
        for role, (email, password) in (("admin", DEMO_USERS["admin"]), ("staff", DEMO_USERS["staff"])):
            db.add(User(email=email, full_name=f"Demo {role.title()}", password_hash=hash_password(password), role=UserRole(role)))
        db.commit()

    api = TestClient(app, base_url="http://localhost")
    _ok(api.post("/api/v1/auth/login", json={"email": DEMO_USERS["admin"][0], "password": DEMO_USERS["admin"][1]}))
    post = lambda path, body=None: _ok(api.post(f"/api/v1{path}", json=body or {}))  # noqa: E731

    gst18 = post("/taxes", {"name": "GST 18%", "rate_percent": "18"})
    gst5 = post("/taxes", {"name": "GST 5%", "rate_percent": "5"})
    crm = post("/products", {"name": "Brightloop CRM seat", "sales_price": "1200.00", "cost_price": "300.00", "tax_id": gst18["id"]})
    crm = post(f"/products/{crm['id']}/variants", {"name": "Standard", "extra_price": "0"})
    crm = post(f"/products/{crm['id']}/variants", {"name": "Premium", "extra_price": "800.00"})
    premium = next(v for v in crm["variants"] if v["name"] == "Premium")
    analytics = post("/products", {"name": "Analytics add-on", "sales_price": "600.00", "tax_id": gst18["id"]})
    kit = post("/products", {"name": "Onboarding kit", "product_type": "goods", "sales_price": "2500.00", "tax_id": gst5["id"]})

    monthly = post("/plans", {"name": "Monthly", "billing_period": "monthly"})
    quarterly = post("/plans", {"name": "Quarterly", "billing_period": "monthly", "billing_interval": 3, "min_quantity": 5})
    post("/plans", {"name": "Annual (12-month term)", "billing_period": "yearly", "duration_periods": 1, "is_pausable": False})
    post("/quotation-templates", {"name": "CRM starter", "plan_id": monthly["id"], "lines": [
        {"product_id": crm["id"], "quantity": "3"}, {"product_id": analytics["id"], "quantity": "1"}]})
    post("/discounts", {"name": "Volume 10% (over ₹20,000)", "discount_type": "percentage", "value": "10", "min_purchase_amount": "20000"})

    acme = post("/customers", {"name": "Acme Retail Pvt Ltd", "email": DEMO_USERS["customer"][0], "phone": "+91 98765 43210", "address": "MG Road, Bengaluru"})
    post(f"/customers/{acme['id']}/portal-access", {"password": DEMO_USERS["customer"][1]})
    globex = post("/customers", {"name": "Globex Logistics", "email": "billing@globex-demo.com", "address": "Andheri East, Mumbai"})
    initech = post("/customers", {"name": "Initech Labs", "email": "accounts@initech-demo.com"})

    def subscribe(customer: dict, plan: dict, start: date, lines: list[dict], activate: bool = True) -> dict:
        q = post("/quotations", {"customer_id": customer["id"], "plan_id": plan["id"], "start_date": start.isoformat(), "lines": lines})
        post(f"/quotations/{q['id']}/send")
        q = post(f"/quotations/{q['id']}/confirm")
        sub_id = q["subscription_id"]
        if activate:
            post(f"/subscriptions/{sub_id}/activate")
        return {"id": sub_id}

    today = date.today()
    acme_sub = subscribe(acme, monthly, today - timedelta(days=95), [
        {"product_id": crm["id"], "variant_id": premium["id"], "quantity": "4"}, {"product_id": analytics["id"], "quantity": "1"}])
    globex_sub = subscribe(globex, quarterly, today - timedelta(days=40), [{"product_id": crm["id"], "quantity": "10"}])
    subscribe(initech, monthly, today, [{"product_id": kit["id"], "quantity": "1"}], activate=False)

    invoices = []
    # Simulate billing having run weekly in the past, so invoice/due dates (and overdue balances) look realistic.
    as_of = today - timedelta(days=95)
    while as_of <= today:
        for sub in (acme_sub, globex_sub):
            r = api.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={"as_of": as_of.isoformat()})
            if r.status_code == 422:  # nothing due yet on this date
                continue
            for inv in _ok(r):
                post(f"/invoices/{inv['id']}/confirm")
                invoices.append(inv)
        as_of += timedelta(days=7)

    acme_invoices = sorted((i for i in invoices if i["customer_id"] == acme["id"]), key=lambda i: i["period_start"])
    if acme_invoices:
        first = acme_invoices[0]
        post("/payments", {"invoice_id": first["id"], "amount": first["total"], "method": "bank_transfer",
                           "payment_date": (date.fromisoformat(first["invoice_date"]) + timedelta(days=5)).isoformat(), "reference": "NEFT-DEMO-001"})
    if len(acme_invoices) > 1:
        post("/payments", {"invoice_id": acme_invoices[1]["id"], "amount": "2000.00", "method": "upi",
                           "payment_date": (date.fromisoformat(acme_invoices[1]["invoice_date"]) + timedelta(days=10)).isoformat(), "reference": "UPI-DEMO-002"})

    # A sent quotation awaiting the portal customer's response.
    q = post("/quotations", {"customer_id": acme["id"], "plan_id": monthly["id"], "start_date": (today + timedelta(days=7)).isoformat(),
                             "lines": [{"product_id": kit["id"], "quantity": "2"}]})
    post(f"/quotations/{q['id']}/send")

    print(f"Seeded {len(invoices)} invoices. Demo logins:")
    for role, (email, password) in DEMO_USERS.items():
        print(f"  {role:<8} {email}  /  {password}")


if __name__ == "__main__":
    main()
