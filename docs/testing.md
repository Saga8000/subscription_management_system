# Testing

## Backend (pytest)

```powershell
cd backend
.venv\Scripts\python -m pytest
```

- Runs against the real PostgreSQL database in `TEST_DATABASE_URL` (`brightloop_sms_test`). The session fixture applies the Alembic migrations, so the migration itself is exercised; every test starts from truncated tables.
- `conftest.py` refuses to run if `TEST_DATABASE_URL` equals `DATABASE_URL`, protecting dev data.
- Tests drive the HTTP API through FastAPI's `TestClient`, so routing, validation, auth cookies, permissions, services and SQL are all covered together.

| File | Covers |
|---|---|
| `test_auth.py` | Registration, email normalisation, duplicate email (409), password policy, role mass-assignment rejection, generic login errors, 401 for anonymous access, logout token revocation, full password-reset flow incl. single-use token and old-token revocation |
| `test_permissions.py` | Staff vs admin restrictions, customers blocked from back-office endpoints, customer isolation (404 on other customers' subscriptions/invoices/quotations, scoped lists), customer accepting a sent quotation, drafts hidden from customers |
| `test_billing.py` | Variant pricing + GST, lifecycle transition rules, idempotent catch-up invoicing (repeat generate + billing run), invoice snapshots surviving catalog changes, re-billing a cancelled period, percentage discount before tax and usage counting, partial/full payments, overpayment / zero / negative / future / pre-invoice-date payment rejection, cancel-after-paid rejection, overdue filter and dashboard consistency, invalid input, presence of the partial unique index |

Last verified result: **22 passed**.

## Frontend

```powershell
cd frontend
npm run typecheck   # tsc --noEmit
npm run build       # typecheck + production bundle
```

Both pass. There are no component unit tests (see decisions.md).

## End-to-end smoke check

With the backend (`:8000`) and `npm run dev` (`:5173`) running on a seeded database:

```powershell
backend\.venv\Scripts\python scripts\smoke_test.py
```

It goes through the Vite proxy exactly like the browser: SPA and deep-link serving, Swagger availability, login for all three demo roles, every staff list endpoint, dashboard, role restrictions, idempotent billing run, customer isolation, pending portal quotation, logout revocation. Last verified result: **all 29 checks passed**.

## Browser verification

A recorded real-browser pass (desktop and a 375px mobile viewport) covered login/logout for all roles, every staff screen, the customer portal, customer creation, quotation → subscription → invoice → payment, billing-run idempotency, payment validation, paid/partial/overdue states, loading and offline-error states, and customer isolation via direct URLs. It found one bug: wide tables overflowed the page on mobile. That is fixed (every table is now in a `.table-wrap` scroll container) and was re-verified. There are no automated frontend/browser tests, so repeat this manually after UI changes.

Evidence in [`media/`](media): the walkthrough video [`brightloop-demo.mp4`](media/brightloop-demo.mp4), the mobile fix re-check [`brightloop-mobile-layout-fix.mp4`](media/brightloop-mobile-layout-fix.mp4), and numbered screenshots (dashboard, customer, subscription, invoice/payment, invoice states, portal, isolation, validation, loading/offline, mobile before/after).
