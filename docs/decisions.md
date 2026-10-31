# Design decisions

| Decision | Reasoning |
|---|---|
| Modular monolith (FastAPI + one PostgreSQL DB) | Fits the team size and hackathon scope; transactions across quotations, subscriptions, invoices and payments stay simple and ACID. |
| Services own business rules; routers stay thin | Rules (transitions, billing, payments) are testable and reused by the API, billing run and seed script. |
| `NUMERIC` money + `Decimal` in Python, strings in JSON | Avoids floating-point errors in financial totals; the browser never does arithmetic on money. |
| Idempotency = row lock + existence check + partial unique index | Defence in depth: the lock serialises concurrent runs, the check skips billed periods, the index makes duplicates impossible even if code changes. Cancelled invoices are excluded so a period can be re-billed after a correction. |
| Catch-up billing (max 24 periods per run) | If billing was not run for a while, one run issues every missed period instead of silently skipping revenue; the cap bounds a single transaction. |
| Invoice date = date billing ran | Invoices cannot be back-dated; due date = invoice date + payment terms. The seed simulates weekly historical runs to produce realistic overdue data. |
| A confirmed subscription auto-activates when billing reaches its start date | Matches how a signed quotation becomes a running subscription without an extra manual step; staff can also activate explicitly. |
| One best discount per invoice, no stacking | Predictable totals; fixed discounts are allocated across lines proportionally (remainder to the largest line) so per-line tax stays exact. Discount applies before tax. |
| Snapshots on quotation/invoice lines | Issued documents never change when catalog prices or tax rates change. |
| JWT in httpOnly cookie + token_version | No token in JS-accessible storage; logout/reset revoke instantly without a token blacklist table. |
| 404 for other customers' records | Prevents leaking which document numbers exist. |
| Sequences for document numbers | Concurrency-safe without table locks; gaps (e.g. rolled-back transactions) are acceptable for these references. |
| No Docker | PostgreSQL 16 is already installed locally; the project rules prohibit Docker unless justified. |
| PowerShell scripts instead of a Makefile | Windows has no `make` by default. |
| No background scheduler (Celery/APScheduler) | Billing is idempotent and exposed via API, so an OS scheduler can call it; avoids extra infrastructure. |
| Seed through the public API | Demo data passes the same validation and business rules as real usage. |

# Limitations

- No email delivery (invoices, quotation notifications, password reset tokens are dev-only).
- No payment gateway — payments are recorded manually by staff (as specified).
- No PDF export of invoices; invoice pages are printable from the browser (print stylesheet hides navigation).
- Single currency (INR); no multi-currency or rounding per currency.
- No proration for mid-period quantity or plan changes; changing a running subscription's lines requires closing and renewing.
- Dashboard MRR is an estimate from active subscription recurring totals normalised to months.
- No login rate limiting or CSRF token (see security.md).
- No frontend unit tests; frontend is verified by TypeScript, the production build and the API smoke check.
