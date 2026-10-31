from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.permissions import customer_scope, ensure_can_access_customer, is_internal
from app.models import Quotation, QuotationLine, Subscription, SubscriptionLine, User
from app.models.enums import QuotationStatus, SubscriptionStatus
from app.schemas.quotation import LineOut
from app.schemas.subscription import SubscriptionListItem, SubscriptionOut
from app.services import audit_service
from app.services.pricing import compute_expiry, compute_line, next_period_start
from app.utils.invoice_number import next_document_number
from app.utils.money import ZERO
from app.utils.pagination import PageParams, paginate

ALLOWED_TRANSITIONS: dict[SubscriptionStatus, set[SubscriptionStatus]] = {
    SubscriptionStatus.CONFIRMED: {SubscriptionStatus.ACTIVE, SubscriptionStatus.CLOSED},
    SubscriptionStatus.ACTIVE: {SubscriptionStatus.PAUSED, SubscriptionStatus.CLOSED},
    SubscriptionStatus.PAUSED: {SubscriptionStatus.ACTIVE, SubscriptionStatus.CLOSED},
    SubscriptionStatus.CLOSED: set(),
}


def _transition(subscription: Subscription, target: SubscriptionStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[subscription.status]:
        raise BusinessRuleError(
            f"Cannot change a {subscription.status.value} subscription to {target.value}."
        )
    subscription.status = target


def _line_out(line: SubscriptionLine) -> LineOut:
    amounts = compute_line(line.quantity, line.unit_price, line.tax.rate_percent if line.tax else None)
    return LineOut(
        id=line.id, product_id=line.product_id, variant_id=line.variant_id, description=line.description,
        quantity=line.quantity, unit_price=line.unit_price, tax_id=line.tax_id, tax_rate=amounts.tax_rate,
        subtotal=amounts.subtotal, tax_amount=amounts.tax_amount, total=amounts.total,
    )


def recurring_total(subscription: Subscription) -> object:
    return sum((_line_out(line).total for line in subscription.lines), ZERO)


def to_out(subscription: Subscription) -> SubscriptionOut:
    lines = [_line_out(line) for line in subscription.lines]
    untaxed = sum((l.subtotal for l in lines), ZERO)
    tax = sum((l.tax_amount for l in lines), ZERO)
    plan = subscription.plan
    return SubscriptionOut(
        id=subscription.id, number=subscription.number, customer_id=subscription.customer_id,
        customer_name=subscription.customer.name, plan_id=plan.id, plan_name=plan.name,
        billing_period=plan.billing_period, billing_interval=plan.billing_interval,
        is_closable=plan.is_closable, is_pausable=plan.is_pausable, is_renewable=plan.is_renewable,
        quotation_id=subscription.quotation_id, quotation_number=subscription.quotation.number,
        status=subscription.status, start_date=subscription.start_date, expiry_date=subscription.expiry_date,
        next_invoice_date=subscription.next_invoice_date, payment_terms_days=subscription.payment_terms_days,
        activated_at=subscription.activated_at, paused_at=subscription.paused_at,
        closed_at=subscription.closed_at, close_reason=subscription.close_reason,
        lines=lines, untaxed_amount=untaxed, tax_total=tax, recurring_total=untaxed + tax,
    )


def to_list_item(subscription: Subscription) -> SubscriptionListItem:
    return SubscriptionListItem(
        id=subscription.id, number=subscription.number, customer_id=subscription.customer_id,
        customer_name=subscription.customer.name, plan_name=subscription.plan.name,
        status=subscription.status, start_date=subscription.start_date,
        expiry_date=subscription.expiry_date, next_invoice_date=subscription.next_invoice_date,
        recurring_total=recurring_total(subscription),  # type: ignore[arg-type]
    )


_LOAD_OPTIONS = (
    selectinload(Subscription.lines).selectinload(SubscriptionLine.tax),
    selectinload(Subscription.customer),
    selectinload(Subscription.plan),
    selectinload(Subscription.quotation),
)


def _load(db: Session, subscription_id: int, *, lock: bool = False) -> Subscription:
    stmt = select(Subscription).where(Subscription.id == subscription_id)
    if lock:
        stmt = stmt.with_for_update()
    subscription = db.scalar(stmt.options(*_LOAD_OPTIONS))
    if subscription is None:
        raise NotFoundError("Subscription not found.")
    return subscription


def get_subscription(db: Session, subscription_id: int, user: User) -> Subscription:
    subscription = _load(db, subscription_id)
    ensure_can_access_customer(user, subscription.customer_id, "Subscription")
    return subscription


def list_subscriptions(
    db: Session, user: User, params: PageParams, status: SubscriptionStatus | None = None,
    customer_id: int | None = None, plan_id: int | None = None, q: str | None = None,
) -> tuple[list[Subscription], int]:
    stmt = select(Subscription).options(*_LOAD_OPTIONS).order_by(Subscription.id.desc())
    scope = customer_scope(user)
    if scope is not None:
        stmt = stmt.where(Subscription.customer_id == scope)
    elif customer_id is not None:
        stmt = stmt.where(Subscription.customer_id == customer_id)
    if status is not None:
        stmt = stmt.where(Subscription.status == status)
    if plan_id is not None:
        stmt = stmt.where(Subscription.plan_id == plan_id)
    if q:
        stmt = stmt.where(Subscription.number.ilike(f"%{q.strip()}%"))
    return paginate(db, stmt, params)


def create_from_quotation(db: Session, quotation: Quotation, *, actor_id: int | None) -> Subscription:
    plan = quotation.plan
    subscription = Subscription(
        number=next_document_number(db, "subscription"),
        customer_id=quotation.customer_id, plan_id=plan.id, quotation_id=quotation.id,
        status=SubscriptionStatus.CONFIRMED, start_date=quotation.start_date,
        expiry_date=compute_expiry(quotation.start_date, plan.billing_period, plan.billing_interval, plan.duration_periods),
        next_invoice_date=quotation.start_date, payment_terms_days=quotation.payment_terms_days,
        created_by_id=actor_id,
        lines=[
            SubscriptionLine(
                product_id=l.product_id, variant_id=l.variant_id, description=l.description,
                quantity=l.quantity, unit_price=l.unit_price, tax_id=l.tax_id,
            )
            for l in quotation.lines
        ],
    )
    db.add(subscription)
    db.flush()
    audit_service.record(db, actor_id=actor_id, action="subscription.create", entity_type="subscription", entity_id=subscription.id, quotation=quotation.number)
    return subscription


def activate(db: Session, subscription_id: int, actor: User) -> Subscription:
    subscription = _load(db, subscription_id, lock=True)
    if subscription.status != SubscriptionStatus.CONFIRMED:
        raise BusinessRuleError(f"Only confirmed subscriptions can be activated (current: {subscription.status.value}).")
    if subscription.start_date > date.today():
        raise BusinessRuleError(f"This subscription starts on {subscription.start_date} and cannot be activated earlier.")
    _transition(subscription, SubscriptionStatus.ACTIVE)
    subscription.activated_at = datetime.now(UTC)
    audit_service.record(db, actor_id=actor.id, action="subscription.activate", entity_type="subscription", entity_id=subscription.id)
    db.commit()
    return _load(db, subscription.id)


def pause(db: Session, subscription_id: int, actor: User) -> Subscription:
    subscription = _load(db, subscription_id, lock=True)
    if not subscription.plan.is_pausable:
        raise BusinessRuleError(f"Plan '{subscription.plan.name}' does not allow pausing.")
    _transition(subscription, SubscriptionStatus.PAUSED)
    subscription.paused_at = datetime.now(UTC)
    audit_service.record(db, actor_id=actor.id, action="subscription.pause", entity_type="subscription", entity_id=subscription.id)
    db.commit()
    return _load(db, subscription.id)


def resume(db: Session, subscription_id: int, actor: User) -> Subscription:
    """Periods that started while paused are not billed; billing resumes at the next period start."""
    subscription = _load(db, subscription_id, lock=True)
    if subscription.status != SubscriptionStatus.PAUSED:
        raise BusinessRuleError(f"Only paused subscriptions can be resumed (current: {subscription.status.value}).")
    _transition(subscription, SubscriptionStatus.ACTIVE)
    plan = subscription.plan
    today = date.today()
    while subscription.next_invoice_date < today:
        subscription.next_invoice_date = next_period_start(
            subscription.start_date, subscription.next_invoice_date, plan.billing_period, plan.billing_interval
        )
    subscription.paused_at = None
    audit_service.record(db, actor_id=actor.id, action="subscription.resume", entity_type="subscription", entity_id=subscription.id)
    db.commit()
    return _load(db, subscription.id)


def close(db: Session, subscription_id: int, user: User, reason: str | None) -> Subscription:
    """Early closure. Customers may close their own subscription only if the plan allows it;
    staff/admin may always close (business override, audited)."""
    subscription = _load(db, subscription_id, lock=True)
    ensure_can_access_customer(user, subscription.customer_id, "Subscription")
    if not is_internal(user) and not subscription.plan.is_closable:
        raise PermissionDeniedError(f"Plan '{subscription.plan.name}' does not allow early closure. Contact Brightloop.")
    _transition(subscription, SubscriptionStatus.CLOSED)
    subscription.closed_at = datetime.now(UTC)
    subscription.close_reason = reason or ("Closed by customer" if not is_internal(user) else "Closed by staff")
    audit_service.record(db, actor_id=user.id, action="subscription.close", entity_type="subscription", entity_id=subscription.id, reason=subscription.close_reason)
    db.commit()
    return _load(db, subscription.id)


def renew(db: Session, subscription_id: int, actor: User) -> Quotation:
    """Creates a draft renewal quotation (same lines and prices) starting after the current term."""
    subscription = _load(db, subscription_id, lock=True)
    if not subscription.plan.is_renewable:
        raise BusinessRuleError(f"Plan '{subscription.plan.name}' is not renewable.")
    if subscription.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.CLOSED):
        raise BusinessRuleError(f"A {subscription.status.value} subscription cannot be renewed.")
    open_renewal = db.scalar(
        select(Quotation.number).where(
            Quotation.renewal_of_id == subscription.id,
            Quotation.status.in_((QuotationStatus.DRAFT, QuotationStatus.SENT)),
        )
    )
    if open_renewal:
        raise ConflictError(f"Renewal quotation {open_renewal} is already open for this subscription.")
    today = date.today()
    start = max(
        today,
        date.fromordinal(subscription.expiry_date.toordinal() + 1) if subscription.expiry_date else subscription.next_invoice_date,
    )
    original = subscription.quotation
    quotation = Quotation(
        number=next_document_number(db, "quotation"), customer_id=subscription.customer_id,
        plan_id=subscription.plan_id, status=QuotationStatus.DRAFT, quotation_date=today,
        expiration_date=date.fromordinal(today.toordinal() + 30), start_date=start,
        payment_terms_days=subscription.payment_terms_days,
        notes=f"Renewal of {subscription.number}", renewal_of_id=subscription.id,
        template_id=original.template_id if original else None, created_by_id=actor.id,
        lines=[
            QuotationLine(
                product_id=l.product_id, variant_id=l.variant_id, description=l.description,
                quantity=l.quantity, unit_price=l.unit_price, tax_id=l.tax_id,
            )
            for l in subscription.lines
        ],
    )
    db.add(quotation)
    db.flush()
    audit_service.record(db, actor_id=actor.id, action="subscription.renew", entity_type="subscription", entity_id=subscription.id, quotation=quotation.number)
    db.commit()
    return quotation
