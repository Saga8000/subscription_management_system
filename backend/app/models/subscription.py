from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import SubscriptionStatus

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.plan import Plan
    from app.models.quotation import Quotation
    from app.models.subscription_line import SubscriptionLine


class Subscription(TimestampMixin, Base):
    """Lifecycle: confirmed -> active <-> paused; active/paused/confirmed -> closed."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("expiry_date IS NULL OR expiry_date > start_date", name="expiry_after_start"),
        CheckConstraint("next_invoice_date >= start_date", name="next_invoice_after_start"),
        CheckConstraint(
            "payment_terms_days >= 0 AND payment_terms_days <= 365", name="payment_terms_range"
        ),
        Index("ix_subscriptions_status_next_invoice_date", "status", "next_invoice_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="RESTRICT"), unique=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        pg_enum(SubscriptionStatus, "subscription_status")
    )
    start_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    # First day of the next period still to be invoiced.
    next_invoice_date: Mapped[date] = mapped_column(Date)
    payment_terms_days: Mapped[int] = mapped_column(default=15, server_default=text("15"))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    customer: Mapped["Customer"] = relationship()
    plan: Mapped["Plan"] = relationship()
    quotation: Mapped["Quotation"] = relationship(
        back_populates="subscription", foreign_keys=[quotation_id]
    )
    lines: Mapped[list["SubscriptionLine"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan", order_by="SubscriptionLine.id"
    )
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="subscription")
