from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.conftest import make_subscription


def test_staff_cannot_manage_users_or_taxes(staff: TestClient) -> None:
    assert staff.get("/api/v1/users").status_code == 403
    r = staff.post("/api/v1/users", json={"email": "s2@example.com", "full_name": "S", "password": "Str0ng!Passw0rd", "role": "admin"})
    assert r.status_code == 403
    assert staff.post("/api/v1/taxes", json={"name": "T", "rate_percent": "5"}).status_code == 403


def test_customer_cannot_reach_back_office_endpoints(register_customer) -> None:
    customer, _ = register_customer("c@example.com")
    assert customer.get("/api/v1/customers").status_code == 403
    assert customer.post("/api/v1/products", json={"name": "X", "sales_price": "1"}).status_code == 403
    assert customer.post("/api/v1/billing/run", json={}).status_code == 403
    assert customer.get("/api/v1/reports/dashboard").status_code == 403


def test_customer_only_sees_own_records(staff: TestClient, catalog, register_customer) -> None:
    alice, alice_id = register_customer("alice@example.com")
    bob, _ = register_customer("bob@example.com")
    sub = make_subscription(staff, catalog, alice_id, date.today() - timedelta(days=5))
    invoices = staff.post(f"/api/v1/subscriptions/{sub['id']}/generate-invoice", json={}).json()
    invoice_id = invoices[0]["id"]
    assert staff.post(f"/api/v1/invoices/{invoice_id}/confirm").status_code == 200

    assert alice.get(f"/api/v1/subscriptions/{sub['id']}").status_code == 200
    assert alice.get(f"/api/v1/invoices/{invoice_id}").status_code == 200
    assert alice.get("/api/v1/invoices").json()["total"] == 1

    # Another customer gets "not found", not "forbidden", so record existence is not leaked.
    assert bob.get(f"/api/v1/subscriptions/{sub['id']}").status_code == 404
    assert bob.get(f"/api/v1/invoices/{invoice_id}").status_code == 404
    assert bob.get(f"/api/v1/quotations/{sub['quotation_id']}").status_code == 404
    assert bob.get("/api/v1/invoices").json()["total"] == 0
    assert bob.get("/api/v1/subscriptions").json()["total"] == 0
    assert bob.post(f"/api/v1/subscriptions/{sub['id']}/close", json={}).status_code == 404


def test_customer_can_accept_a_sent_quotation(staff: TestClient, catalog, register_customer) -> None:
    customer, customer_id = register_customer("q@example.com")
    r = staff.post(
        "/api/v1/quotations",
        json={"customer_id": customer_id, "plan_id": catalog["plan"]["id"], "start_date": date.today().isoformat(),
              "lines": [{"product_id": catalog["product"]["id"], "quantity": "1"}]},
    )
    quotation_id = r.json()["id"]
    assert customer.get(f"/api/v1/quotations/{quotation_id}").status_code == 404  # drafts are internal
    staff.post(f"/api/v1/quotations/{quotation_id}/send")
    r = customer.post(f"/api/v1/quotations/{quotation_id}/confirm")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    assert r.json()["subscription_id"] is not None
