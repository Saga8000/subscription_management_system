from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.permissions import ensure_can_access_customer
from app.models import Invoice, InvoiceLine, Subscription, User
from app.models.enums import DiscountType, InvoiceStatus, SubscriptionStatus
from app.schemas.invoice import InvoiceLineOut, InvoiceListItem, InvoiceOut
from app.schemas.payment import PaymentOut
from app.services import audit_service, discount_service
from app.services.pricing import BillableLine
from app.utils.invoice_number import next_document_number
from app.utils.money import ZERO, percent_of


def is_overdue(invoice: Invoice, today: date) -> bool:
    return (
        invoice.status == InvoiceStatus.CONFIRMED
        and invoice.due_date < today
        and invoice.amount_paid < invoice.total
    )


def to_list_item(invoice: Invoice, today: date) -> InvoiceListItem:
    return InvoiceListItem(
        id=invoice.id,
        number=invoice.number,
        subscription_id=invoice.subscription_id,
        customer_id=invoice.customer_id,
        customer_name=invoice.customer_name,
        status=invoice.status,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        total=invoice.total,
        amount_paid=invoice.amount_paid,
        amount_due=invoice.amount_due,
        is_overdue=is_overdue(invoice, today),
    )


def to_out(invoice: Invoice, today: date) -> InvoiceOut:
    return InvoiceOut(
        **to_list_item(invoice, today).model_dump(),
        subscription_number=invoice.subscription.number,
        customer_email=invoice.customer_email,
        customer_address=invoice.customer_address,
        subtotal=invoice.subtotal,
        discount_total=invoice.discount_total,
        discount_description=invoice.discount_description,
        untaxed_amount=invoice.untaxed_amount,
        tax_total=invoice.tax_total,
        confirmed_at=invoice.confirmed_at,
        paid_at=invoice.paid_at,
        cancelled_at=invoice.cancelled_at,
        lines=[InvoiceLineOut.model_validate(line) for line in invoice.lines],
        payments=[PaymentOut.model_validate(p) for p in invoice.payments],
    )


def get_invoice(db: Session, invoice_id: int, user: User) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.payments),
            selectinload(Invoice.subscription),
        )
    )
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    ensure_can_access_customer(user, invoice.customer_id, "Invoice")
    return invoice


def _billable_lines(subscription: Subscription) -> list[BillableLine]:
    return [
        BillableLine(
            product_id=line.product_id,
            variant_id=line.variant_id,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            tax_name=line.tax.name if line.tax else None,
            tax_rate=line.tax.rate_percent if line.tax else ZERO,
        )
        for line in subscription.lines
    ]


def _discount_label(discount_type: DiscountType, value: object, name: str) -> str:
    suffix = f"{value}%" if discount_type == DiscountType.PERCENTAGE else f"{value} off"
    return f"{name} ({suffix})"[:160]


def build_invoice(
    db: Session,
    subscription: Subscription,
    *,
    period_start: date,
    period_end: date,
    invoice_date: date,
    actor_id: int | None,
) -> Invoice:
    """Creates a draft invoice from the subscription's current lines (snapshotted).
    Caller owns the transaction and must hold a lock on the subscription row."""
    lines = _billable_lines(subscription)
    if not lines:
        raise BusinessRuleError(f"Subscription {subscription.number} has no lines to bill.")

    chosen = discount_service.best_discount(db, subscription.id, lines, invoice_date)
    discount_amounts = chosen[1] if chosen else [ZERO for _ in lines]
    if chosen:
        discount_service.consume_usage(db, chosen[0].id)

    invoice_lines: list[InvoiceLine] = []
    for line, discount_amount in zip(lines, discount_amounts, strict=True):
        taxable = line.subtotal - discount_amount
        tax_amount = percent_of(taxable, line.tax_rate)
        invoice_lines.append(
            InvoiceLine(
                product_id=line.product_id,
                variant_id=line.variant_id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_subtotal=line.subtotal,
                discount_amount=discount_amount,
                tax_name=line.tax_name,
                tax_rate=line.tax_rate,
                tax_amount=tax_amount,
                line_total=taxable + tax_amount,
            )
        )

    subtotal = sum((il.line_subtotal for il in invoice_lines), ZERO)
    discount_total = sum((il.discount_amount for il in invoice_lines), ZERO)
    tax_total = sum((il.tax_amount for il in invoice_lines), ZERO)
    untaxed = subtotal - discount_total
    customer = subscription.customer

    invoice = Invoice(
        number=next_document_number(db, "invoice"),
        subscription_id=subscription.id,
        customer_id=customer.id,
        status=InvoiceStatus.DRAFT,
        invoice_date=invoice_date,
        due_date=invoice_date + timedelta(days=subscription.payment_terms_days),
        period_start=period_start,
        period_end=period_end,
        customer_name=customer.name,
        customer_email=customer.email,
        customer_address=customer.address,
        subtotal=subtotal,
        discount_total=discount_total,
        untaxed_amount=untaxed,
        tax_total=tax_total,
        total=untaxed + tax_total,
        amount_paid=ZERO,
        discount_id=chosen[0].id if chosen else None,
        discount_description=(
            _discount_label(chosen[0].discount_type, chosen[0].value, chosen[0].name) if chosen else None
        ),
        created_by_id=actor_id,
        lines=invoice_lines,
    )
    db.add(invoice)
    db.flush()
    audit_service.record(
        db, actor_id=actor_id, action="invoice.create", entity_type="invoice", entity_id=invoice.id,
        subscription=subscription.number, period_start=period_start, total=invoice.total,
    )
    return invoice


def mark_confirmed(invoice: Invoice) -> None:
    now = datetime.now(UTC)
    invoice.status = InvoiceStatus.CONFIRMED
    invoice.confirmed_at = now
    if invoice.total == ZERO:
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = now


def _lock(db: Session, invoice_id: int) -> Invoice:
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id).with_for_update()
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    return invoice


def confirm_invoice(db: Session, invoice_id: int, actor: User) -> None:
    invoice = _lock(db, invoice_id)
    if invoice.status != InvoiceStatus.DRAFT:
        raise BusinessRuleError(f"Only draft invoices can be confirmed (current: {invoice.status.value}).")
    mark_confirmed(invoice)
    audit_service.record(db, actor_id=actor.id, action="invoice.confirm", entity_type="invoice", entity_id=invoice.id)
    db.commit()


def cancel_invoice(db: Session, invoice_id: int, actor: User) -> None:
    """Cancels an unpaid invoice. If it was the latest billed period of a live subscription,
    the subscription's next invoice date is rolled back so the period is billed again."""
    invoice = _lock(db, invoice_id)
    if invoice.status not in (InvoiceStatus.DRAFT, InvoiceStatus.CONFIRMED):
        raise BusinessRuleError(f"A {invoice.status.value} invoice cannot be cancelled.")
    if invoice.amount_paid > 0:
        raise BusinessRuleError("An invoice with recorded payments cannot be cancelled.")

    subscription = db.execute(
        select(Subscription).where(Subscription.id == invoice.subscription_id).with_for_update()
    ).scalar_one()
    invoice.status = InvoiceStatus.CANCELLED
    invoice.cancelled_at = datetime.now(UTC)
    if invoice.discount_id is not None:
        discount_service.release_usage(db, invoice.discount_id)
    if (
        subscription.status != SubscriptionStatus.CLOSED
        and invoice.period_end + timedelta(days=1) >= subscription.next_invoice_date
        and invoice.period_start < subscription.next_invoice_date
    ):
        subscription.next_invoice_date = invoice.period_start
    audit_service.record(db, actor_id=actor.id, action="invoice.cancel", entity_type="invoice", entity_id=invoice.id)
    db.commit()
