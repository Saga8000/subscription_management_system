from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, pg_enum
from app.models.enums import InvoiceStatus

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.invoice_line import InvoiceLine
    from app.models.payment import Payment
    from app.models.subscription import Subscription


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        # One live invoice per subscription billing period (cancelled ones may be re-issued).
        Index(
            "uq_invoices_subscription_period_active",
            "subscription_id",
            "period_start",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
        ),
        Index("ix_invoices_status_due_date", "status", "due_date"),
        CheckConstraint("period_end >= period_start", name="period_range"),
        CheckConstraint("due_date >= invoice_date", name="due_after_invoice"),
        CheckConstraint(
            "subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0", name="amounts_non_negative"
        ),
        CheckConstraint("discount_total <= subtotal", name="discount_within_subtotal"),
        CheckConstraint("untaxed_amount = subtotal - discount_total", name="untaxed_consistent"),
        CheckConstraint("total = untaxed_amount + tax_total", name="total_consistent"),
        CheckConstraint("amount_paid >= 0 AND amount_paid <= total", name="amount_paid_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="RESTRICT"), index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[InvoiceStatus] = mapped_column(pg_enum(InvoiceStatus, "invoice_status"))
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date] = mapped_column(Date)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    # Snapshot of billing details at issue time.
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(254))
    customer_address: Mapped[str | None] = mapped_column(Text)

    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    discount_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    untaxed_amount: Mapped[Decimal] = mapped_column(MONEY)
    tax_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(MONEY)
    amount_paid: Mapped[Decimal] = mapped_column(
        MONEY, default=Decimal("0"), server_default=text("0")
    )

    discount_id: Mapped[int | None] = mapped_column(
        ForeignKey("discounts.id", ondelete="SET NULL")
    )
    discount_description: Mapped[str | None] = mapped_column(String(160))

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    subscription: Mapped["Subscription"] = relationship(back_populates="invoices")
    customer: Mapped["Customer"] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLine.id"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", order_by="Payment.payment_date"
    )

    @property
    def amount_due(self) -> Decimal:
        return self.total - self.amount_paid
