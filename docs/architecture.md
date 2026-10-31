# Architecture

```
Browser (React SPA, :5173)
   │  same-origin /api requests (Vite dev proxy) + httpOnly auth cookie
   ▼
FastAPI (:8000)  app/main.py
   ├── api/v1/*          thin routers: parse/validate (Pydantic), auth dependency, call a service
   ├── services/*        business rules, transactions, row locks, audit events
   ├── models/*          SQLAlchemy 2 declarative models (source of truth for Alembic)
   ├── schemas/*         Pydantic request/response models (extra="forbid" on inputs)
   └── core/*            settings, security (Argon2/JWT), permissions, error handlers
   ▼
PostgreSQL 16  (brightloop_sms; tests use brightloop_sms_test)
```

## Backend layout (`backend/app`)

| Path | Responsibility |
|---|---|
| `config.py` | Settings from `.env` (pydantic-settings) |
| `database.py` | Engine, session factory, `get_db` dependency |
| `dependencies.py` | Resolves the current user from cookie or `Authorization: Bearer` |
| `core/permissions.py` | `require_admin`, `require_staff`, `require_any_user`, customer scoping |
| `core/exceptions.py` | `AppError` hierarchy → consistent `{"error": {code, message, fields}}` bodies |
| `services/pricing.py` | Pure functions: line totals, variant price, billing-period calendar, MRR |
| `services/quotation_service.py` | Quotation CRUD and transitions; confirm creates a subscription |
| `services/subscription_service.py` | Lifecycle transitions (activate/pause/resume/close), renewals |
| `services/billing_service.py` | Due-subscription discovery, catch-up billing, auto-close on expiry |
| `services/invoice_service.py` | Invoice snapshots, discount/tax totals, confirm/cancel |
| `services/payment_service.py` | Locked payment recording, overpayment prevention, paid status |
| `services/report_service.py` | Dashboard aggregates in SQL |
| `seed.py` | Demo data loaded through the public API |

## Frontend layout (`frontend/src`)

| Path | Responsibility |
|---|---|
| `api/client.ts` | Typed fetch wrapper, `ApiError` with field errors, global 401 handling |
| `context/AuthContext.tsx` | Current user, login/register/logout |
| `context/ToastContext.tsx` | Success/error notifications |
| `components/Layout.tsx` | Role-aware sidebar/header layout; routes are protected by role in `App.tsx` |
| `components/ui.tsx` | Loading/error/empty states, pagination, modal, confirm dialog, form field |
| `pages/*` | Dashboard, catalog, plans, templates, quotations, subscriptions, invoices, payments, discounts, taxes, users, customer portal, auth pages |

Decimal amounts travel as JSON strings and are only formatted (never computed) in the browser; the server is the single source of financial truth.

## Main business flow

1. Staff creates a **quotation** (customer, plan, product/variant lines; optional template) → **send**.
2. Staff or the customer (portal) **confirms** it → a **subscription** is created in `confirmed` status with copied lines.
3. The subscription becomes `active` on **activate**, or automatically when billing runs on/after its start date.
4. **Billing** (`POST /billing/run` or per-subscription *Generate invoice*) creates one invoice per due period, applying the best eligible discount and per-line taxes, and advances `next_invoice_date`.
5. Staff **confirms** invoices and **records payments** (partial allowed). The invoice becomes `paid` when the balance reaches zero; confirmed invoices past their due date are **overdue**.
6. Subscriptions can be paused/resumed/closed, and **renewed** (creates a new draft quotation).

## Scheduling

Billing is triggered manually from the dashboard ("Run billing") or via the API. The run is idempotent, so it can safely be scheduled once a day with Windows Task Scheduler calling `POST /api/v1/billing/run` with a staff token. No scheduler is bundled (see decisions.md).
