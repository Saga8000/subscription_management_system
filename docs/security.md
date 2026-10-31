# Security

## Authentication

- Passwords hashed with **Argon2** (`argon2-cffi`). Policy: more than 8 characters, upper- and lower-case letter, and a special character — enforced server-side.
- Login returns a **JWT (HS256)** in an `httpOnly`, `SameSite=Strict` cookie (`Secure` when `COOKIE_SECURE=true`). Lifetime `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480).
- Tokens carry the user's `token_version`; **logout and password reset increment it**, revoking every outstanding token (tested).
- Login errors are identical for unknown email and wrong password; forgot-password always returns the same message, so accounts cannot be enumerated.
- Password reset tokens are random (`secrets`), stored only as SHA-256 hashes, single-use, and expire after `PASSWORD_RESET_TOKEN_MINUTES`. Because no email provider is configured, the raw token is returned in the API response **only when `APP_ENV=development`**.

## Authorization

- Role checks are FastAPI dependencies (`require_admin`, `require_staff`, `require_any_user`) on every route.
- **Customer isolation**: queries for customers are scoped to their own `customer_id` in the service layer; records owned by someone else return **404** (not 403) so their existence is not revealed. Draft quotations are invisible to customers.
- Self-registration always creates a *customer* role; `role` and other privileged fields are rejected (`extra="forbid"`), preventing mass assignment. Registration never auto-links an existing customer record by email — staff must grant portal access explicitly.

## Data protection and input handling

- All SQL goes through SQLAlchemy expressions with bound parameters (no string-built SQL from user input).
- Every request body is a Pydantic model with length limits, numeric bounds and enums.
- Error responses never include stack traces or SQL; unexpected errors are logged server-side and return a generic 500 body. Integrity errors become a generic 409.
- CORS allows only origins listed in `CORS_ORIGINS`; in development the Vite proxy makes API calls same-origin.
- Secrets live only in `.env` (git-ignored). `scripts/create_database.ps1` generates a random DB password and a 64-character JWT secret and never prints the PostgreSQL superuser password.
- State changes are written to `audit_logs` with the acting user.

## Known limitations

- No rate limiting / account lockout on login (would add e.g. a reverse-proxy limit in production).
- No CSRF token: mitigated by `SameSite=Strict` cookies and JSON-only endpoints, but a token would be needed if cookies were relaxed to `Lax`/`None`.
- Password reset delivery is development-only (no email integration).
- HTTPS termination is expected from a production reverse proxy; set `COOKIE_SECURE=true` there.
