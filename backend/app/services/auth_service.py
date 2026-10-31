from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AuthenticationError, BusinessRuleError, ConflictError, NotFoundError
from app.core.security import (
    generate_reset_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import Customer, User
from app.models.enums import UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, UserOut
from app.schemas.user import StaffCreate, UserUpdate
from app.services import audit_service


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        customer_id=user.customer.id if user.customer else None,
    )


def _ensure_email_free(db: Session, email: str) -> None:
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("An account with this email already exists.", fields={"email": "Already registered"})


def register_customer(db: Session, data: RegisterRequest) -> User:
    _ensure_email_free(db, data.email)
    if db.scalar(select(Customer.id).where(Customer.email == data.email)) is not None:
        # Never auto-link an existing customer record by email: that would expose its invoices
        # to anyone who registers with that address.
        raise ConflictError(
            "This email belongs to an existing customer. Ask Brightloop staff to enable portal access.",
            fields={"email": "Existing customer"},
        )
    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=UserRole.CUSTOMER,
    )
    user.customer = Customer(name=data.full_name, email=data.email)
    db.add(user)
    db.flush()
    audit_service.record(db, actor_id=user.id, action="user.register", entity_type="user", entity_id=user.id)
    db.commit()
    return user


def authenticate(db: Session, data: LoginRequest) -> User:
    user = db.scalar(select(User).where(User.email == data.email))
    valid = verify_password(data.password, user.password_hash if user else None)
    if user is None or not valid or not user.is_active:
        raise AuthenticationError("Invalid email or password.")
    return user


def logout(db: Session, user: User) -> None:
    user.token_version += 1
    db.commit()


def request_password_reset(db: Session, email: str) -> str | None:
    """Returns the raw token (for the development-only flow) or None if no such active user."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return None
    raw, token_hash = generate_reset_token()
    user.password_reset_token_hash = token_hash
    user.password_reset_expires_at = datetime.now(UTC) + timedelta(
        minutes=get_settings().password_reset_token_minutes
    )
    db.commit()
    return raw


def reset_password(db: Session, token: str, new_password: str) -> None:
    user = db.scalar(select(User).where(User.password_reset_token_hash == hash_token(token)))
    if (
        user is None
        or user.password_reset_expires_at is None
        or user.password_reset_expires_at < datetime.now(UTC)
    ):
        raise BusinessRuleError("This reset link is invalid or has expired.")
    user.password_hash = hash_password(new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.token_version += 1
    audit_service.record(db, actor_id=user.id, action="user.password_reset", entity_type="user", entity_id=user.id)
    db.commit()


# --- Admin user management ----------------------------------------------------------------


def list_users(db: Session, role: UserRole | None = None) -> list[User]:
    stmt = select(User).order_by(User.role, User.email)
    if role is not None:
        stmt = stmt.where(User.role == role)
    return list(db.scalars(stmt).all())


def create_staff(db: Session, data: StaffCreate, actor: User) -> User:
    _ensure_email_free(db, data.email)
    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=UserRole(data.role),
    )
    db.add(user)
    db.flush()
    audit_service.record(db, actor_id=actor.id, action="user.create", entity_type="user", entity_id=user.id, role=data.role)
    db.commit()
    return user


def update_user(db: Session, user_id: int, data: UserUpdate, actor: User) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    if data.is_active is False and user.id == actor.id:
        raise BusinessRuleError("You cannot deactivate your own account.")
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.is_active is not None and data.is_active != user.is_active:
        user.is_active = data.is_active
        user.token_version += 1
    audit_service.record(db, actor_id=actor.id, action="user.update", entity_type="user", entity_id=user.id)
    db.commit()
    return user


def enable_portal_access(db: Session, customer_id: int, password: str, actor: User) -> User:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError("Customer not found.")
    if customer.user_id is not None:
        raise ConflictError("This customer already has portal access.")
    _ensure_email_free(db, customer.email)
    user = User(
        email=customer.email,
        full_name=customer.name,
        password_hash=hash_password(password),
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    db.flush()
    customer.user_id = user.id
    audit_service.record(db, actor_id=actor.id, action="customer.portal_access", entity_type="customer", entity_id=customer.id)
    db.commit()
    return user
