from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, QUANTITY, Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.product_variant import ProductVariant
    from app.models.quotation import Quotation
    from app.models.tax import Tax


class QuotationLine(Base):
    __tablename__ = "quotation_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="RESTRICT")
    )
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY)
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"))

    quotation: Mapped["Quotation"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()
    variant: Mapped["ProductVariant | None"] = relationship()
    tax: Mapped["Tax | None"] = relationship()
