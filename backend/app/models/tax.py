from decimal import Decimal

from sqlalchemy import CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import PERCENT, Base, TimestampMixin


class Tax(TimestampMixin, Base):
    __tablename__ = "taxes"
    __table_args__ = (
        CheckConstraint("rate_percent >= 0 AND rate_percent <= 100", name="rate_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    rate_percent: Mapped[Decimal] = mapped_column(PERCENT)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
