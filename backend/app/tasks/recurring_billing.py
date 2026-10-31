"""Command-line billing run, e.g. for Windows Task Scheduler:

    python -m app.tasks.recurring_billing [--as-of YYYY-MM-DD] [--auto-confirm]
"""

import argparse
from datetime import date

from app.database import SessionLocal
from app.services.billing_service import run_billing


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate due recurring invoices.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--auto-confirm", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        result = run_billing(db, as_of=args.as_of, actor_id=None, auto_confirm=args.auto_confirm)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
