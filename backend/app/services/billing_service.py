"""Recurring billing.

Guarantees:
* Idempotent: a subscription period is invoiced at most once. Enforced by checking for an
  existing live invoice under a row lock on the subscription AND by the partial unique index
  `uq_invoices_subscription_period_active` (subscription_id, period_start) WHERE status <> 'cancelled'.
* Isolated: each subscription is billed in its own transaction; a failure is rolled back and
  reported without affecting other subscriptions in the batch.
"""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, BusinessRuleError, NotFoundError
from app.models import Invoice, Subscription, User
from app.models.enums import InvoiceStatus, SubscriptionStatus
from app.schemas.invoice import BillingFailure, BillingRunResult
from app.services import audit_service, invoice_service
from app.services.pricing import next_period_start

logger = logging.getLogger("app.billing")

MAX_PERIODS_PER_RUN = 24


def _lock_subscription(db: Session, subscription_id: int) -> Subscription:
    subscription = db.execute(
        select(Subscription).where(Subscription.id == subscription_id).with_for_update()
    ).scalar_one_or_none()
    if subscription is None:
        raise NotFoundError("Subscription not found.")
    return subscription


def bill_subscription(
    db: Session,
    subscription_id: int,
    *,
    as_of: date,
    actor_id: int | None,
    auto_confirm: bool = False,
) -> tuple[list[Invoice], bool]:
    """Invoices every due period up to `as_of`. Returns (created invoices, closed?).
    Does not commit."""
    subscription = _lock_subscription(db, subscription_id)
    now = datetime.now(UTC)

    if subscription.status == SubscriptionStatus.CONFIRMED and subscription.start_date <= as_of:
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.activated_at = now
        audit_service.record(db, actor_id=actor_id, action="subscription.activate", entity_type="subscription", entity_id=subscription.id)

    if subscription.status != SubscriptionStatus.ACTIVE:
        return [], False

    plan = subscription.plan
    created: list[Invoice] = []
    for _ in range(MAX_PERIODS_PER_RUN):
        period_start = subscription.next_invoice_date
        if period_start > as_of:
            break
        if subscription.expiry_date and period_start > subscription.expiry_date:
            break
        following = next_period_start(
            subscription.start_date, period_start, plan.billing_period, plan.billing_interval
        )
        period_end = following - timedelta(days=1)
        if subscription.expiry_date:
            period_end = min(period_end, subscription.expiry_date)

        already_billed = db.scalar(
            select(Invoice.id).where(
                Invoice.subscription_id == subscription.id,
                Invoice.period_start == period_start,
                Invoice.status != InvoiceStatus.CANCELLED,
            )
        )
        if already_billed is None:
            invoice = invoice_service.build_invoice(
                db, subscription, period_start=period_start, period_end=period_end,
                invoice_date=as_of, actor_id=actor_id,
            )
            if auto_confirm:
                invoice_service.mark_confirmed(invoice)
            created.append(invoice)
        subscription.next_invoice_date = following

    closed = False
    if (
        subscription.expiry_date
        and as_of > subscription.expiry_date
        and subscription.next_invoice_date > subscription.expiry_date
        and plan.auto_close
    ):
        subscription.status = SubscriptionStatus.CLOSED
        subscription.closed_at = now
        subscription.close_reason = "Expired"
        closed = True
        audit_service.record(db, actor_id=actor_id, action="subscription.expire", entity_type="subscription", entity_id=subscription.id)
    return created, closed


def generate_now(db: Session, subscription_id: int, *, as_of: date, actor: User) -> list[Invoice]:
    """Manual "Generate invoice" for one subscription."""
    created, _ = bill_subscription(db, subscription_id, as_of=as_of, actor_id=actor.id)
    if not created:
        subscription = db.get(Subscription, subscription_id)
        db.rollback()
        if subscription is None:
            raise NotFoundError("Subscription not found.")
        if subscription.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.CONFIRMED):
            raise BusinessRuleError(f"A {subscription.status.value} subscription is not billed.")
        raise BusinessRuleError(
            f"Nothing to invoice: the next billing period starts on {subscription.next_invoice_date}."
        )
    db.commit()
    return created


def due_subscriptions(db: Session, as_of: date) -> list[tuple[int, str]]:
    rows = db.execute(
        select(Subscription.id, Subscription.number)
        .where(
            or_(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    or_(
                        Subscription.next_invoice_date <= as_of,
                        Subscription.expiry_date < as_of,
                    ),
                ),
                and_(
                    Subscription.status == SubscriptionStatus.CONFIRMED,
                    Subscription.start_date <= as_of,
                ),
            )
        )
        .order_by(Subscription.id)
    ).all()
    return [(row.id, row.number) for row in rows]


def run_billing(
    db: Session, *, as_of: date, actor_id: int | None, auto_confirm: bool = False
) -> BillingRunResult:
    candidates = due_subscriptions(db, as_of)
    created_numbers: list[str] = []
    closed_numbers: list[str] = []
    failures: list[BillingFailure] = []

    for subscription_id, number in candidates:
        try:
            created, closed = bill_subscription(
                db, subscription_id, as_of=as_of, actor_id=actor_id, auto_confirm=auto_confirm
            )
            db.commit()
            created_numbers.extend(inv.number for inv in created)
            if closed:
                closed_numbers.append(number)
        except AppError as exc:
            db.rollback()
            failures.append(BillingFailure(subscription_id=subscription_id, subscription_number=number, error=exc.message))
        except IntegrityError:
            db.rollback()
            failures.append(
                BillingFailure(
                    subscription_id=subscription_id, subscription_number=number,
                    error="Skipped: period already invoiced by a concurrent billing run.",
                )
            )
        except Exception:  # noqa: BLE001 - one bad record must not abort the batch
            db.rollback()
            logger.exception("Billing failed for subscription %s", number)
            failures.append(
                BillingFailure(subscription_id=subscription_id, subscription_number=number, error="Unexpected error; see server log.")
            )

    audit_service.record(
        db, actor_id=actor_id, action="billing.run", entity_type="billing", entity_id=None,
        as_of=as_of, checked=len(candidates), created=len(created_numbers), failed=len(failures),
    )
    db.commit()
    return BillingRunResult(
        as_of=as_of,
        subscriptions_checked=len(candidates),
        invoices_created=created_numbers,
        subscriptions_closed=closed_numbers,
        failures=failures,
    )
