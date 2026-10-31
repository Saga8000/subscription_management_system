from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, pg_enum
from app.models.enums import ProductType

if TYPE_CHECKING:
    from app.models.product_variant import ProductVariant
    from app.models.tax import Tax


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("sales_price >= 0", name="sales_price_non_negative"),
        CheckConstraint("cost_price >= 0", name="cost_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    product_type: Mapped[ProductType] = mapped_column(pg_enum(ProductType, "product_type"))
    sales_price: Mapped[Decimal] = mapped_column(MONEY)
    cost_price: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    tax: Mapped["Tax | None"] = relationship()
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", order_by="ProductVariant.name"
    )
