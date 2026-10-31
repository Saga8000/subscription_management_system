from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, pg_enum
from app.models.enums import PaymentMethod

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class Payment(TimestampMixin, Base):
    """Manually recorded payment against one invoice. Several payments = partial payments."""

    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)
    method: Mapped[PaymentMethod] = mapped_column(pg_enum(PaymentMethod, "payment_method"))
    payment_date: Mapped[date] = mapped_column(Date, index=True)
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
