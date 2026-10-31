from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Column, Date, ForeignKey, String, Table, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, QUANTITY, Base, TimestampMixin, pg_enum
from app.models.enums import DiscountType

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.subscription import Subscription

discount_products = Table(
    "discount_products",
    Base.metadata,
    Column("discount_id", ForeignKey("discounts.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
)

discount_subscriptions = Table(
    "discount_subscriptions",
    Base.metadata,
    Column("discount_id", ForeignKey("discounts.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "subscription_id", ForeignKey("subscriptions.id", ondelete="CASCADE"), primary_key=True
    ),
)


class Discount(TimestampMixin, Base):
    """Admin-configured discount rule. Empty product/subscription lists = applies to all."""

    __tablename__ = "discounts"
    __table_args__ = (
        CheckConstraint("value > 0", name="value_positive"),
        CheckConstraint(
            "discount_type <> 'percentage' OR value <= 100", name="percentage_max_100"
        ),
        CheckConstraint(
            "min_purchase_amount IS NULL OR min_purchase_amount >= 0", name="min_purchase_range"
        ),
        CheckConstraint("min_quantity IS NULL OR min_quantity > 0", name="min_quantity_range"),
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until >= valid_from",
            name="validity_range",
        ),
        CheckConstraint("usage_limit IS NULL OR usage_limit >= 1", name="usage_limit_positive"),
        CheckConstraint(
            "usage_count >= 0 AND (usage_limit IS NULL OR usage_count <= usage_limit)",
            name="usage_within_limit",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    discount_type: Mapped[DiscountType] = mapped_column(pg_enum(DiscountType, "discount_type"))
    value: Mapped[Decimal] = mapped_column(MONEY)
    min_purchase_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    min_quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    usage_limit: Mapped[int | None]
    usage_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    products: Mapped[list["Product"]] = relationship(secondary=discount_products)
    subscriptions: Mapped[list["Subscription"]] = relationship(secondary=discount_subscriptions)
