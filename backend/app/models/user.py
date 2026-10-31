from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.customer import Customer


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    # Incremented on logout / password change to invalidate previously issued tokens.
    token_version: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(128))
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped["Customer | None"] = relationship(back_populates="user")
