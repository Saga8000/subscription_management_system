# Database design

PostgreSQL 16. Schema is defined by SQLAlchemy models in `backend/app/models` and versioned with Alembic (`backend/alembic/versions`). The initial migration creates 20 tables, 8 enum types, 40 CHECK constraints, 38 foreign keys and 3 sequences (verified against `brightloop_sms`, including a full downgrade → upgrade round trip).

## Conventions

- Money: `NUMERIC(12,2)`; tax rates `NUMERIC(6,3)`; quantities `NUMERIC(12,2)`. Never floats. Rounding is `ROUND_HALF_UP` to 2 decimals in Python before storing.
- Timestamps: `timestamptz` (`created_at`, `updated_at` with server defaults). Business dates (`start_date`, `invoice_date`, `due_date`, `payment_date`) are `date`.
- Constraint names follow a naming convention (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`) so migrations are deterministic.
- Document numbers (`QT-000001`, `SUB-000001`, `INV-000001`) come from PostgreSQL sequences `quotation_number_seq`, `subscription_number_seq`, `invoice_number_seq` (concurrency-safe; gaps are acceptable).

## Tables

| Table | Purpose / key rules |
|---|---|
| `users` | Login accounts; `role` enum (admin/staff/customer); unique lower-cased email; `token_version` for revocation; reset-token hash + expiry |
| `customers` | Billing contacts; unique email; optional 1:1 `user_id` for portal access |
| `taxes` | Name + rate (0–100) |
| `products` | `product_type` (service/goods), sales/cost price ≥ 0, optional tax |
| `product_variants` | Per-product unique name, `extra_price` adjustment (base + extra ≥ 0 enforced in service) |
| `plans` | Billing period (daily/weekly/monthly/yearly) × interval, min quantity, optional duration, availability window, closable/pausable/renewable/auto-close flags |
| `quotation_templates`, `quotation_template_lines` | Reusable line sets for a plan |
| `quotations`, `quotation_lines` | Status enum (draft/sent/confirmed/cancelled), expiry, start date, payment terms; lines snapshot price and tax |
| `subscriptions`, `subscription_lines` | Status enum (confirmed/active/paused/closed), `next_invoice_date`, `expiry_date`, 1:1 with its quotation |
| `discounts` (+ `discount_products`, `discount_subscriptions`) | Percentage or fixed, validity window, min purchase, usage limit/count, optional product/subscription scope |
| `invoices`, `invoice_lines` | Status enum (draft/confirmed/paid/cancelled); period start/end; subtotal, discount, untaxed, tax, total, amount_paid; lines snapshot description, product/variant, price, discount, tax name/rate/amount |
| `payments` | Many per invoice (partial payments); `amount > 0`; method enum |
| `audit_logs` | Actor, action, entity, JSON details for every state change |

## Integrity guarantees

- **No duplicate recurring invoices**: partial unique index
  `uq_invoices_subscription_period_active ON invoices (subscription_id, period_start) WHERE status <> 'cancelled'`.
  Billing also locks the subscription row (`SELECT … FOR UPDATE`) and checks for an existing invoice before inserting, so concurrent or repeated runs cannot double-bill. A cancelled invoice frees its period for re-billing.
- **No overpayment**: the invoice row is locked while a payment is recorded; amount must be ≤ outstanding balance (service) and `amount_paid <= total` (CHECK).
- **Lifecycle**: enum columns plus explicit transition tables in services reject invalid transitions with 422.
- **Financial snapshots**: invoice and quotation lines copy prices and tax rates, so later catalog changes never alter issued documents (covered by a test).
- Foreign keys use `RESTRICT` for financial records (payments, invoices) and `CASCADE` only for owned child lines.

## Migration workflow

```powershell
cd backend
.venv\Scripts\alembic upgrade head                      # apply
.venv\Scripts\alembic revision --autogenerate -m "msg"  # after changing models; review the file before committing
.venv\Scripts\alembic downgrade -1                      # roll back one revision
```

Autogenerate does not detect sequences or enum-type drops; the initial migration adds those by hand.
