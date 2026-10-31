from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models import Invoice, Payment, User
from app.models.enums import InvoiceStatus
from app.schemas.payment import PaymentCreate, PaymentListItem
from app.services import audit_service


def to_list_item(payment: Payment) -> PaymentListItem:
    return PaymentListItem(
        id=payment.id,
        invoice_id=payment.invoice_id,
        amount=payment.amount,
        method=payment.method,
        payment_date=payment.payment_date,
        reference=payment.reference,
        note=payment.note,
        created_at=payment.created_at,
        invoice_number=payment.invoice.number,
        customer_name=payment.invoice.customer_name,
    )


def record_payment(db: Session, data: PaymentCreate, actor: User) -> Payment:
    """Records a manual payment. The invoice row is locked so concurrent payments cannot
    over-pay it; the invoice becomes Paid when the balance reaches zero."""
    invoice = db.execute(
        select(Invoice).where(Invoice.id == data.invoice_id).with_for_update()
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    if invoice.status == InvoiceStatus.PAID:
        raise BusinessRuleError("This invoice is already fully paid.")
    if invoice.status != InvoiceStatus.CONFIRMED:
        raise BusinessRuleError(
            f"Payments can only be recorded against confirmed invoices (current: {invoice.status.value})."
        )
    if data.payment_date > date.today():
        raise BusinessRuleError("Payment date cannot be in the future.", fields={"payment_date": "Future date"})
    outstanding = invoice.total - invoice.amount_paid
    if data.amount > outstanding:
        raise BusinessRuleError(
            f"Amount exceeds the outstanding balance of {outstanding}.",
            fields={"amount": f"Maximum is {outstanding}"},
        )

    payment = Payment(
        invoice_id=invoice.id,
        amount=data.amount,
        method=data.method,
        payment_date=data.payment_date,
        reference=data.reference,
        note=data.note,
        recorded_by_id=actor.id,
    )
    invoice.amount_paid = invoice.amount_paid + data.amount
    if invoice.amount_paid == invoice.total:
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.now(UTC)
    db.add(payment)
    db.flush()
    audit_service.record(
        db, actor_id=actor.id, action="payment.record", entity_type="invoice", entity_id=invoice.id,
        payment_id=payment.id, amount=data.amount,
    )
    db.commit()
    db.refresh(payment)
    return payment
