"""Test setup: runs Alembic migrations against TEST_DATABASE_URL and truncates every table between tests.

The application engine is bound to DATABASE_URL at import time, so DATABASE_URL is pointed at the
test database *before* any `app` module is imported.
"""

import os
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent


def _env_value(key: str) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return None


TEST_DATABASE_URL = _env_value("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is not set (see .env.example / scripts/create_database.ps1).")
if TEST_DATABASE_URL == _env_value("DATABASE_URL"):
    raise RuntimeError("TEST_DATABASE_URL must differ from DATABASE_URL: tests truncate every table.")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["APP_ENV"] = "development"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.models.enums import UserRole  # noqa: E402

PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def clean_tables(migrated_database: None) -> Iterator[None]:
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


def create_user(email: str, role: UserRole, password: str = PASSWORD) -> None:
    with SessionLocal() as db:
        db.add(User(email=email, full_name=email.split("@")[0].title(), password_hash=hash_password(password), role=role))
        db.commit()


def login(email: str, password: str = PASSWORD) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def anon() -> TestClient:
    return TestClient(app)


@pytest.fixture
def admin() -> TestClient:
    create_user("admin@example.com", UserRole.ADMIN)
    return login("admin@example.com")


@pytest.fixture
def staff() -> TestClient:
    create_user("staff@example.com", UserRole.STAFF)
    return login("staff@example.com")


@pytest.fixture
def register_customer() -> Callable[[str], tuple[TestClient, int]]:
    def _register(email: str) -> tuple[TestClient, int]:
        client = TestClient(app)
        r = client.post("/api/v1/auth/register", json={"email": email, "full_name": email.split("@")[0].title(), "password": PASSWORD})
        assert r.status_code == 201, r.text
        return client, r.json()["customer_id"]

    return _register


@pytest.fixture
def catalog(admin: TestClient) -> dict[str, Any]:
    """GST 18% tax, a product with a Premium variant (+500) and a monthly plan."""
    tax = admin.post("/api/v1/taxes", json={"name": "GST 18%", "rate_percent": "18"}).json()
    product = admin.post(
        "/api/v1/products", json={"name": "Cloud Suite", "sales_price": "1000.00", "cost_price": "400.00", "tax_id": tax["id"]}
    ).json()
    product = admin.post(f"/api/v1/products/{product['id']}/variants", json={"name": "Premium", "extra_price": "500.00"}).json()
    plan = admin.post("/api/v1/plans", json={"name": "Monthly", "billing_period": "monthly"}).json()
    return {"tax": tax, "product": product, "variant": product["variants"][0], "plan": plan}


def make_subscription(
    client: TestClient, catalog: dict[str, Any], customer_id: int, start: date, *, quantity: str = "2", activate: bool = True
) -> dict[str, Any]:
    r = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": customer_id,
            "plan_id": catalog["plan"]["id"],
            "start_date": start.isoformat(),
            "payment_terms_days": 15,
            "lines": [{"product_id": catalog["product"]["id"], "variant_id": catalog["variant"]["id"], "quantity": quantity}],
        },
    )
    assert r.status_code == 201, r.text
    quotation = r.json()
    assert client.post(f"/api/v1/quotations/{quotation['id']}/send").status_code == 200
    r = client.post(f"/api/v1/quotations/{quotation['id']}/confirm")
    assert r.status_code == 200, r.text
    sub_id = r.json()["subscription_id"]
    if activate:
        r = client.post(f"/api/v1/subscriptions/{sub_id}/activate")
        assert r.status_code == 200, r.text
    return client.get(f"/api/v1/subscriptions/{sub_id}").json()
