from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from tests.conftest import make_subscription

D = Decimal


def _customer(staff: TestClient, email: str = "acme@example.com") -> int:
    r = staff.post("/api/v1/customers", json={"name": "Acme", "email": email})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_variant_pricing_and_tax_on_quotation(staff: TestClient, catalog) -> None:
    sub = make_subscription(staff, catalog, _customer(staff), date.today(), activate=False)
    line = sub["lines"][0]
    assert D(line["unit_price"]) == D("1500")  # 1000 base + 500 Premium
    assert D(sub["untaxed_amount"]) == D("3000")
    assert D(sub["tax_total"]) == D("540")
    assert D(sub["recurring_total"]) == D("3540")
    assert sub["status"] == "confirmed"


def test_invalid_lifecycle_transitions_are_rejected(staff: TestClient, catalog) -> None:
    sub = make_subscription(staff, catalog, _customer(staff), date.today(), activate=False)
    sid = sub["id"]
    assert staff.post(f"/api/v1/subscriptions/{sid}/resume").status_code in (409, 422)
    assert staff.post(f"/api/v1/subscriptions/{sid}/activate").status_code == 200
    assert staff.post(f"/api/v1/subscriptions/{sid}/activate").status_code in (409, 422)
    assert staff.post(f"/api/v1/subscriptions/{sid}/pause").json()["status"] == "paused"
    assert staff.post(f"/api/v1/subscriptions/{sid}/resume").json()["status"] == "active"
    assert staff.post(f"/api/v1/subscriptions/{sid}/close", json={"reason": "test"}).json()["status"] == "closed"
    for action in ("activate", "pause", "resume"):
        assert staff.post(f"/api/v1/subscriptions/{sid}/{action}").status_code in (409, 422), action
    assert staff.post(f"/api/v1/quotations/{sub['quotation_id']}/cancel").status_code in (409, 422)


def test_invoice_generation_is_idempotent(staff: TestClient, catalog) -> None:
    sub = make_subscription(staff, catalog, _customer(staff), date.today() - timedelta(days=65))
    first = staff.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={})
    assert first.status_code == 200, first.text
    created = first.json()
    assert len(created) >= 3  # catch-up: one invoice per elapsed monthly period
    starts = [i["period_start"] for i in created]
    assert len(set(starts)) == len(starts)

    again = staff.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={})
    assert again.status_code in (200, 422)
    run = staff.post("/api/v1/billing/run", json={})
    assert run.status_code == 200 and run.json()["invoices_created"] == []
    assert staff.get("/api/v1/invoices", params={"subscription_id": sub["id"]}).json()["total"] == len(created)

    inv = staff.get(f"/api/v1/invoices/{created[0]['id']}").json()
    assert D(inv["subtotal"]) == D("3000") and D(inv["tax_total"]) == D("540") and D(inv["total"]) == D("3540")
    assert inv["lines"][0]["tax_name"] == "GST 18%"


def test_invoice_snapshot_survives_catalog_changes(admin: TestClient, staff: TestClient, catalog) -> None:
    sub = make_subscription(staff, catalog, _customer(staff), date.today())
    invoice = staff.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={}).json()[0]
    admin.patch(f"/api/v1/taxes/{catalog['tax']['id']}", json={"rate_percent": "28"})
    admin.patch(f"/api/v1/products/{catalog['product']['id']}", json={"sales_price": "9999.00"})
    again = staff.get(f"/api/v1/invoices/{invoice['id']}").json()
    assert D(again["total"]) == D("3540")
    assert D(again["lines"][0]["tax_rate"]) == D("18")


def test_cancelled_period_can_be_billed_again(staff: TestClient, catalog) -> None:
    sub = make_subscription(staff, catalog, _customer(staff), date.today())
    invoice = staff.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={}).json()[0]
    assert staff.post(f"/api/v1/invoices/{invoice['id']}/cancel").json()["status"] == "cancelled"
    regenerated = staff.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={})
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()[0]["period_start"] == invoice["period_start"]


def test_percentage_discount_applied_before_tax(admin: TestClient, staff: TestClient, catalog) -> None:
    r = admin.post("/api/v1/discounts", json={"name": "Launch 10%", "discount_type": "percentage", "value": "10"})
    assert r.status_code == 201, r.text
    sub = make_subscription(staff, catalog, _customer(staff), date.today())
    inv = staff.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={}).json()[0]
    assert D(inv["discount_total"]) == D("300")
    assert D(inv["untaxed_amount"]) == D("2700")
    assert D(inv["tax_total"]) == D("486")
    assert D(inv["total"]) == D("3186")
    assert admin.get(f"/api/v1/discounts/{r.json()['id']}").json()["usage_count"] == 1


def test_partial_full_and_over_payments(staff: TestClient, catalog) -> None:
    sub = make_subscription(staff, catalog, _customer(staff), date.today())
    invoice = staff.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={}).json()[0]
    pay = {"invoice_id": invoice["id"], "method": "upi", "payment_date": date.today().isoformat()}

    assert staff.post("/api/v1/payments", json={**pay, "amount": "100"}).status_code == 422  # draft invoice
    staff.post(f"/api/v1/invoices/{invoice['id']}/confirm")

    assert staff.post("/api/v1/payments", json={**pay, "amount": "1000"}).status_code == 201
    inv = staff.get(f"/api/v1/invoices/{invoice['id']}").json()
    assert inv["status"] == "confirmed" and D(inv["amount_paid"]) == D("1000") and D(inv["amount_due"]) == D("2540")

    assert staff.post("/api/v1/payments", json={**pay, "amount": "2540.01"}).status_code == 422
    assert staff.post("/api/v1/payments", json={**pay, "amount": "0"}).status_code == 422
    assert staff.post("/api/v1/payments", json={**pay, "amount": "-5"}).status_code == 422
    future = (date.today() + timedelta(days=2)).isoformat()
    assert staff.post("/api/v1/payments", json={**pay, "amount": "10", "payment_date": future}).status_code == 422
    before_invoice = (date.fromisoformat(invoice["invoice_date"]) - timedelta(days=1)).isoformat()
    assert staff.post("/api/v1/payments", json={**pay, "amount": "10", "payment_date": before_invoice}).status_code == 422

    assert staff.post("/api/v1/payments", json={**pay, "amount": "2540"}).status_code == 201
    inv = staff.get(f"/api/v1/invoices/{invoice['id']}").json()
    assert inv["status"] == "paid" and D(inv["amount_due"]) == 0 and len(inv["payments"]) == 2
    assert staff.post("/api/v1/payments", json={**pay, "amount": "1"}).status_code == 422
    assert staff.post(f"/api/v1/invoices/{invoice['id']}/cancel").status_code in (409, 422)


def test_overdue_filter_matches_due_dates(staff: TestClient, catalog) -> None:
    sub = make_subscription(staff, catalog, _customer(staff), date.today() - timedelta(days=95))
    for inv in staff.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={}).json():
        staff.post(f"/api/v1/invoices/{inv['id']}/confirm")
    items = staff.get("/api/v1/invoices", params={"page_size": 100}).json()["items"]
    today = date.today().isoformat()
    expected = {i["id"] for i in items if i["status"] == "confirmed" and i["due_date"] < today}
    overdue = staff.get("/api/v1/invoices", params={"overdue": "true", "page_size": 100}).json()["items"]
    assert {i["id"] for i in overdue} == expected
    assert all(i["is_overdue"] for i in overdue)
    dashboard = staff.get("/api/v1/reports/dashboard").json()
    assert dashboard["overdue_count"] == len(expected)
    assert D(dashboard["outstanding_balance"]) == sum(D(i["amount_due"]) for i in items if i["status"] == "confirmed")


def test_invalid_input_is_rejected(staff: TestClient, catalog) -> None:
    assert staff.post("/api/v1/products", json={"name": "Bad", "sales_price": "-1"}).status_code == 422
    assert staff.post("/api/v1/products", json={"name": "", "sales_price": "1"}).status_code == 422
    assert staff.post("/api/v1/plans", json={"name": "P", "billing_period": "hourly"}).status_code == 422
    cid = _customer(staff)
    assert staff.post("/api/v1/customers", json={"name": "Dup", "email": "acme@example.com"}).status_code == 409
    r = staff.post(
        "/api/v1/quotations",
        json={"customer_id": cid, "plan_id": catalog["plan"]["id"], "start_date": date.today().isoformat(),
              "lines": [{"product_id": catalog["product"]["id"], "quantity": "0"}]},
    )
    assert r.status_code == 422
    assert staff.get("/api/v1/invoices/999999").status_code == 404


def test_database_enforces_invoice_period_uniqueness() -> None:
    with engine.connect() as conn:
        indexdef = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_invoices_subscription_period_active'")
        ).scalar_one()
    assert "UNIQUE" in indexdef and "cancelled" in indexdef
