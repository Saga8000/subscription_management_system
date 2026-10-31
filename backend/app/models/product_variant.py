from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product


class ProductVariant(TimestampMixin, Base):
    """A product option that adjusts the base price, e.g. "Odoo brand" (+560)."""

    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("product_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    extra_price: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    product: Mapped["Product"] = relationship(back_populates="variants")

    @property
    def unit_price(self) -> Decimal:
        return self.product.sales_price + self.extra_price
