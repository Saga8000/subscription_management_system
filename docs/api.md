# API

Base path: `/api/v1`. Full, always-current reference with request/response schemas, query filters and a "Try it out" console: **http://127.0.0.1:8000/docs** (Swagger UI) or `/redoc`; raw spec at `/openapi.json`. Health check: `GET /health`.

Authentication: `POST /auth/login` sets the `sms_access_token` httpOnly cookie. API clients may instead send `Authorization: Bearer <token>`.

Larger lists (customers, products, quotations, subscriptions, invoices, payments) are paginated: `{"items": [...], "total", "page", "page_size"}` with `?page=` and `?page_size=`.

## Errors

Every error has the same shape:

```json
{"error": {"code": "validation_error", "message": "Some fields are invalid.", "fields": {"email": "value is not a valid email address"}}}
```

| Status | `code` | When |
|---|---|---|
| 401 | `unauthenticated` | Missing/expired/revoked token, bad credentials |
| 403 | `forbidden` | Authenticated but role not allowed |
| 404 | `not_found` | Missing record, or a record owned by another customer |
| 409 | `conflict` | Duplicate email/name, unique-constraint violation |
| 422 | `validation_error` / `business_rule_violation` | Invalid input, invalid lifecycle transition, overpayment, nothing to bill |

## Endpoints

| Area | Endpoints | Access |
|---|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/forgot-password`, `POST /auth/reset-password` | public / signed-in |
| Users | `GET /users`, `POST /users`, `PATCH /users/{id}` | admin |
| Customers | `GET /customers`, `POST /customers`, `PATCH /customers/{id}`, `POST /customers/{id}/portal-access` | staff |
| | `GET /customers/{id}` | staff / that customer |
| Taxes | `GET /taxes` | staff |
| | `POST /taxes`, `PATCH /taxes/{id}` | admin |
| Products | `GET /products`, `GET /products/{id}` | signed-in |
| | `POST /products`, `PATCH /products/{id}`, `POST /products/{id}/variants`, `PATCH /products/{id}/variants/{variant_id}` | staff |
| Plans | `GET /plans`, `GET /plans/{id}` | signed-in |
| | `POST /plans`, `PATCH /plans/{id}` | staff |
| Quotation templates | `GET /quotation-templates`, `POST /quotation-templates`, `PATCH /quotation-templates/{id}` | staff |
| Quotations | `GET /quotations`, `GET /quotations/{id}` | staff / owning customer (non-draft only) |
| | `POST /quotations`, `PATCH /quotations/{id}`, `POST /quotations/{id}/send` | staff |
| | `POST /quotations/{id}/confirm`, `POST /quotations/{id}/cancel` | staff / owning customer |
| Subscriptions | `GET /subscriptions`, `GET /subscriptions/{id}` | staff / owning customer |
| | `POST /subscriptions/{id}/activate`, `/pause`, `/resume`, `/renew`, `/generate-invoice` | staff |
| | `POST /subscriptions/{id}/close` | staff / owning customer (if the plan is closable) |
| Billing | `POST /billing/run` `{"as_of": "YYYY-MM-DD"?, "auto_confirm": false}` | staff |
| Invoices | `GET /invoices` (filters incl. `status`, `overdue`, `q`), `GET /invoices/{id}` | staff / owning customer |
| | `POST /invoices/{id}/confirm`, `POST /invoices/{id}/cancel` | staff |
| Payments | `GET /payments` | staff / owning customer |
| | `POST /payments` | staff |
| Discounts | `GET /discounts`, `GET /discounts/{id}` | staff |
| | `POST /discounts`, `PUT /discounts/{id}` | admin |
| Reports | `GET /reports/dashboard` | staff |

Role requirements are enforced server-side in each router (`backend/app/api/v1`); the frontend only hides actions for convenience.

## Example

```bash
curl -c jar -H "Content-Type: application/json" \
  -d '{"email":"staff@brightloop-demo.com","password":"Staff@Demo2026"}' \
  http://127.0.0.1:8000/api/v1/auth/login
curl -b jar -X POST -H "Content-Type: application/json" -d '{}' http://127.0.0.1:8000/api/v1/billing/run
# → {"as_of":"…","subscriptions_checked":N,"invoices_created":["INV-000005"],"subscriptions_closed":[],"failures":[]}
```
