from datetime import date

from sqlalchemy import CheckConstraint, Date, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import BillingPeriod


class Plan(TimestampMixin, Base):
    """Recurring plan: defines billing cadence and lifecycle options, not prices."""

    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("billing_interval >= 1", name="interval_positive"),
        CheckConstraint("min_quantity >= 1", name="min_quantity_positive"),
        CheckConstraint(
            "duration_periods IS NULL OR duration_periods >= 1", name="duration_positive"
        ),
        CheckConstraint(
            "available_from IS NULL OR available_until IS NULL "
            "OR available_until >= available_from",
            name="availability_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    billing_period: Mapped[BillingPeriod] = mapped_column(pg_enum(BillingPeriod, "billing_period"))
    billing_interval: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    min_quantity: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    available_from: Mapped[date | None] = mapped_column(Date)
    available_until: Mapped[date | None] = mapped_column(Date)
    # Number of billing periods before the subscription expires; NULL = open-ended.
    duration_periods: Mapped[int | None]
    is_closable: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    is_pausable: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    is_renewable: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    # Close automatically once the expiry date is reached by billing.
    auto_close: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
