from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import QUANTITY, Base, TimestampMixin, pg_enum
from app.models.enums import QuotationStatus

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.plan import Plan
    from app.models.product import Product
    from app.models.product_variant import ProductVariant
    from app.models.quotation_line import QuotationLine
    from app.models.subscription import Subscription


class QuotationTemplate(TimestampMixin, Base):
    __tablename__ = "quotation_templates"
    __table_args__ = (CheckConstraint("validity_days >= 1", name="validity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    validity_days: Mapped[int] = mapped_column(default=30, server_default=text("30"))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    plan: Mapped["Plan"] = relationship()
    lines: Mapped[list["QuotationTemplateLine"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="QuotationTemplateLine.id"
    )


class QuotationTemplateLine(Base):
    __tablename__ = "quotation_template_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("quotation_templates.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="RESTRICT")
    )
    quantity: Mapped[Decimal] = mapped_column(QUANTITY)

    template: Mapped[QuotationTemplate] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()
    variant: Mapped["ProductVariant | None"] = relationship()


class Quotation(TimestampMixin, Base):
    """Pre-contract document. Lifecycle: draft -> sent ("Quotation") -> confirmed | cancelled.
    Confirming creates exactly one Subscription."""

    __tablename__ = "quotations"
    __table_args__ = (
        CheckConstraint("expiration_date >= quotation_date", name="expiration_after_date"),
        CheckConstraint(
            "payment_terms_days >= 0 AND payment_terms_days <= 365", name="payment_terms_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("quotation_templates.id", ondelete="SET NULL")
    )
    status: Mapped[QuotationStatus] = mapped_column(
        pg_enum(QuotationStatus, "quotation_status"), index=True
    )
    quotation_date: Mapped[date] = mapped_column(Date)
    expiration_date: Mapped[date] = mapped_column(Date)
    start_date: Mapped[date] = mapped_column(Date)
    payment_terms_days: Mapped[int] = mapped_column(default=15, server_default=text("15"))
    notes: Mapped[str | None] = mapped_column(Text)
    renewal_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="RESTRICT", use_alter=True)
    )
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    customer: Mapped["Customer"] = relationship()
    plan: Mapped["Plan"] = relationship()
    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan", order_by="QuotationLine.id"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="quotation", foreign_keys="Subscription.quotation_id"
    )
