from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, PERCENT, QUANTITY, Base

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class InvoiceLine(Base):
    """Immutable snapshot of what was billed; never recomputed from current product data."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint(
            "discount_amount >= 0 AND discount_amount <= line_subtotal", name="discount_range"
        ),
        CheckConstraint("tax_amount >= 0", name="tax_non_negative"),
        CheckConstraint(
            "line_total = line_subtotal - discount_amount + tax_amount", name="total_consistent"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY)
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    line_subtotal: Mapped[Decimal] = mapped_column(MONEY)
    discount_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    tax_name: Mapped[str | None] = mapped_column(String(80))
    tax_rate: Mapped[Decimal] = mapped_column(PERCENT, default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(MONEY)

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")
