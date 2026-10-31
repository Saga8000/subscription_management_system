from fastapi.testclient import TestClient

from tests.conftest import PASSWORD


def test_register_creates_customer_account_and_signs_in(anon: TestClient) -> None:
    r = anon.post("/api/v1/auth/register", json={"email": "New@Example.com", "full_name": "New User", "password": PASSWORD})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "customer"
    assert body["customer_id"] is not None
    assert "password_hash" not in body
    assert anon.get("/api/v1/auth/me").json()["email"] == "new@example.com"


def test_duplicate_email_is_rejected_case_insensitively(anon: TestClient) -> None:
    payload = {"email": "dup@example.com", "full_name": "Dup", "password": PASSWORD}
    assert anon.post("/api/v1/auth/register", json=payload).status_code == 201
    r = TestClient(anon.app).post("/api/v1/auth/register", json={**payload, "email": "DUP@example.com"})
    assert r.status_code == 409
    assert r.json()["error"]["fields"]["email"]


def test_weak_password_is_rejected(anon: TestClient) -> None:
    for weak in ["Short!1", "alllowercase!", "ALLUPPERCASE!", "NoSpecialChar1"]:
        r = anon.post("/api/v1/auth/register", json={"email": "weak@example.com", "full_name": "W", "password": weak})
        assert r.status_code == 422, weak
        assert "password" in r.json()["error"]["fields"]


def test_role_cannot_be_mass_assigned_on_register(anon: TestClient) -> None:
    r = anon.post("/api/v1/auth/register", json={"email": "x@example.com", "full_name": "X", "password": PASSWORD, "role": "admin"})
    assert r.status_code == 422


def test_login_failures_are_generic(anon: TestClient) -> None:
    anon.post("/api/v1/auth/register", json={"email": "a@example.com", "full_name": "A", "password": PASSWORD})
    fresh = TestClient(anon.app)
    wrong_password = fresh.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "Wrong!Passw0rd"})
    unknown_user = fresh.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown_user.json()["error"]["message"]


def test_unauthenticated_requests_are_rejected(anon: TestClient) -> None:
    assert anon.get("/api/v1/auth/me").status_code == 401
    assert anon.get("/api/v1/invoices").status_code == 401


def test_logout_revokes_existing_token(anon: TestClient) -> None:
    anon.post("/api/v1/auth/register", json={"email": "out@example.com", "full_name": "Out", "password": PASSWORD})
    token = anon.cookies.get("sms_access_token")
    assert token
    assert anon.post("/api/v1/auth/logout").status_code == 200
    replay = TestClient(anon.app)
    assert replay.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_password_reset_flow(anon: TestClient) -> None:
    anon.post("/api/v1/auth/register", json={"email": "reset@example.com", "full_name": "R", "password": PASSWORD})
    old_token = anon.cookies.get("sms_access_token")
    r = anon.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    assert r.status_code == 200
    token = r.json()["dev_reset_token"]
    assert token
    unknown = anon.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})
    assert unknown.status_code == 200 and unknown.json()["message"] == r.json()["message"]

    new_password = "N3w!Passw0rd"
    assert anon.post("/api/v1/auth/reset-password", json={"token": token, "new_password": new_password}).status_code == 200
    assert anon.post("/api/v1/auth/reset-password", json={"token": token, "new_password": new_password}).status_code in (400, 401, 422)

    fresh = TestClient(anon.app)
    assert fresh.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": PASSWORD}).status_code == 401
    assert fresh.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": new_password}).status_code == 200
    assert TestClient(anon.app).get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
