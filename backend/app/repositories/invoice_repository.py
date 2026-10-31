from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from app.models import Invoice, Payment
from app.models.enums import InvoiceStatus


def invoice_list_stmt(
    *,
    customer_scope: int | None,
    today: date,
    status: InvoiceStatus | None = None,
    customer_id: int | None = None,
    subscription_id: int | None = None,
    overdue: bool | None = None,
    q: str | None = None,
) -> Select[tuple[Invoice]]:
    stmt = select(Invoice).options(selectinload(Invoice.subscription)).order_by(Invoice.id.desc())
    if customer_scope is not None:
        # Customers never see internal drafts.
        stmt = stmt.where(Invoice.customer_id == customer_scope, Invoice.status != InvoiceStatus.DRAFT)
    elif customer_id is not None:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    if subscription_id is not None:
        stmt = stmt.where(Invoice.subscription_id == subscription_id)
    overdue_clause = (
        (Invoice.status == InvoiceStatus.CONFIRMED)
        & (Invoice.due_date < today)
        & (Invoice.amount_paid < Invoice.total)
    )
    if overdue is True:
        stmt = stmt.where(overdue_clause)
    elif overdue is False:
        stmt = stmt.where(~overdue_clause)
    if q:
        stmt = stmt.where(Invoice.number.ilike(f"%{q.strip()}%"))
    return stmt


def payment_list_stmt(
    *,
    customer_scope: int | None,
    invoice_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Select[tuple[Payment]]:
    stmt = (
        select(Payment)
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .options(selectinload(Payment.invoice))
        .order_by(Payment.payment_date.desc(), Payment.id.desc())
    )
    if customer_scope is not None:
        stmt = stmt.where(Invoice.customer_id == customer_scope)
    if invoice_id is not None:
        stmt = stmt.where(Payment.invoice_id == invoice_id)
    if date_from is not None:
        stmt = stmt.where(Payment.payment_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Payment.payment_date <= date_to)
    return stmt
