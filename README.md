# Brightloop Software — Subscription Management System

A full-stack application that replaces Brightloop's spreadsheet-based subscription tracking: products and variants, recurring plans, quotations, subscription lifecycle, idempotent recurring invoicing with taxes and discounts, manual/partial payments, overdue tracking, a revenue dashboard, and a customer self-service portal.

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Database | PostgreSQL 16 (fixed-point `NUMERIC` money, partial unique indexes, row locks) |
| Auth | Argon2 password hashing, JWT in an httpOnly `SameSite=Strict` cookie, role-based access |
| Frontend | React 18, TypeScript, Vite, React Router |
| Tests | pytest + FastAPI TestClient against a real PostgreSQL test database |

## Demo

- **Video walkthrough:** _VIDEO_URL_PLACEHOLDER_ (replace with the public YouTube/Google Drive link)
- Shows: admin login and dashboard, customer creation, quotation → subscription activation, invoice generation and payment recording, customer data isolation and logout.

## Quick start (Windows)

Prerequisites: Python 3.11+, Node 20+, PostgreSQL 16 running on `localhost:5432`.

```powershell
# 1. Create the app role, both databases and .env (prompts for the postgres superuser password)
powershell -ExecutionPolicy Bypass -File scripts\create_database.ps1
#    Forgot the postgres password? From an Administrator PowerShell:
#    powershell -ExecutionPolicy Bypass -File scripts\reset_postgres_password.ps1

# 2. Install dependencies, run migrations and load demo data
powershell -ExecutionPolicy Bypass -File scripts\setup_dev.ps1 -Seed

# 3. Run (two terminals)
cd backend;  .venv\Scripts\uvicorn app.main:app --reload --port 8000
cd frontend; npm run dev
```

Open http://localhost:5173. Interactive API docs: http://127.0.0.1:8000/docs.

### Demo accounts (created by `python -m app.seed`)

| Role | Email | Password |
|---|---|---|
| Admin | admin@brightloop-demo.com | Admin@Demo2026 |
| Staff | staff@brightloop-demo.com | Staff@Demo2026 |
| Customer (portal) | ananya@acme-demo.com | Customer@Demo2026 |

These are demo-only credentials for a local database; all demo companies and people are fictitious.

## Roles

- **Admin** — everything, including user management and taxes.
- **Staff** — customers, catalog, plans, quotations, subscriptions, invoices, payments, discounts, billing runs, dashboard.
- **Customer** — portal only: own subscriptions, quotations (accept/decline), invoices, payments. Other customers' records return 404.

## Common commands

```powershell
cd backend
.venv\Scripts\python -m pytest                       # backend test suite (uses TEST_DATABASE_URL)
.venv\Scripts\alembic upgrade head                   # apply migrations
.venv\Scripts\alembic revision --autogenerate -m "…" # new migration after model changes
.venv\Scripts\python -m app.seed                     # demo data (empty database only)

cd ..\frontend
npm run typecheck
npm run build

cd ..
backend\.venv\Scripts\python scripts\smoke_test.py   # end-to-end check against running dev servers
```

## Documentation

- [Architecture](docs/architecture.md)
- [Database design](docs/database.md)
- [API](docs/api.md)
- [Security](docs/security.md)
- [Testing](docs/testing.md)
- [Design decisions and limitations](docs/decisions.md)
