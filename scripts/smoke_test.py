"""End-to-end smoke check against the running dev servers (through the Vite proxy, like the browser).

Prereqs: backend on :8000, frontend `npm run dev` on :5173, demo data from `python -m app.seed`.
Usage: backend\\.venv\\Scripts\\python scripts\\smoke_test.py [base_url]
"""

import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173"  # Vite may bind only ::1 on Windows
failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -> {detail}'}")
    if not condition:
        failures.append(label)


def session(email: str, password: str) -> httpx.Client:
    client = httpx.Client(base_url=BASE, timeout=15)
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    check(f"login {email}", r.status_code == 200, r.text)
    return client


with httpx.Client(base_url=BASE, timeout=15) as anon:
    check("SPA index served", "<div id=\"root\">" in anon.get("/").text)
    check("SPA deep link served", anon.get("/invoices/1").status_code == 200)
    check("API docs reachable via backend", httpx.get("http://127.0.0.1:8000/docs", timeout=15).status_code == 200)
    check("unauthenticated /me is 401", anon.get("/api/v1/auth/me").status_code == 401)

staff = session("staff@brightloop-demo.com", "Staff@Demo2026")
me = staff.get("/api/v1/auth/me").json()
check("staff role", me.get("role") == "staff", me)
dash = staff.get("/api/v1/reports/dashboard")
check("dashboard loads", dash.status_code == 200, dash.text)
if dash.status_code == 200:
    d = dash.json()
    print(f"      active={d['active_subscriptions']} outstanding={d['outstanding_balance']} overdue={d['overdue_count']}")
for path in ("/customers", "/products", "/plans", "/quotations", "/subscriptions", "/invoices", "/payments", "/discounts", "/taxes", "/quotation-templates"):
    r = staff.get(f"/api/v1{path}")
    check(f"staff GET {path}", r.status_code == 200, r.text[:200])
check("staff cannot list users", staff.get("/api/v1/users").status_code == 403)
first_run = staff.post("/api/v1/billing/run", json={})
check("billing run succeeds", first_run.status_code == 200 and first_run.json()["failures"] == [], first_run.text[:300])
rerun = staff.post("/api/v1/billing/run", json={})
check("billing re-run creates no duplicates", rerun.status_code == 200 and rerun.json()["invoices_created"] == [], rerun.text[:300])

admin = session("admin@brightloop-demo.com", "Admin@Demo2026")
check("admin lists users", admin.get("/api/v1/users").status_code == 200)

customer = session("ananya@acme-demo.com", "Customer@Demo2026")
check("customer blocked from customers list", customer.get("/api/v1/customers").status_code == 403)
own = customer.get("/api/v1/invoices").json()
check("customer sees only own invoices", own["total"] > 0 and {i["customer_name"] for i in own["items"]} == {"Acme Retail Pvt Ltd"}, own)
other = staff.get("/api/v1/invoices", params={"q": "", "page_size": 100}).json()["items"]
foreign = [i for i in other if i["customer_name"] != "Acme Retail Pvt Ltd"]
if foreign:
    check("customer gets 404 on another customer's invoice", customer.get(f"/api/v1/invoices/{foreign[0]['id']}").status_code == 404)
sent = customer.get("/api/v1/quotations", params={"status": "sent"}).json()
check("customer sees pending quotation", sent["total"] >= 1, sent)
check("logout", customer.post("/api/v1/auth/logout").status_code == 200)
check("session revoked after logout", customer.get("/api/v1/auth/me").status_code == 401)

print(f"\n{'ALL PASSED' if not failures else f'{len(failures)} FAILED'}")
sys.exit(1 if failures else 0)
