from collections.abc import Callable

from fastapi import Depends

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.dependencies import get_current_user
from app.models import User
from app.models.enums import UserRole


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("You do not have permission to perform this action.")
        return user

    return dependency


require_admin = require_roles(UserRole.ADMIN)
require_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)
require_any_user = require_roles(UserRole.ADMIN, UserRole.STAFF, UserRole.CUSTOMER)


def is_internal(user: User) -> bool:
    return user.role in (UserRole.ADMIN, UserRole.STAFF)


def customer_scope(user: User) -> int | None:
    """Customer id the user is restricted to, or None for internal users."""
    if is_internal(user):
        return None
    if user.customer is None:
        raise PermissionDeniedError("Your account is not linked to a customer profile.")
    return user.customer.id


def ensure_can_access_customer(user: User, customer_id: int, entity: str = "Record") -> None:
    """Customers may only see their own records. Responds 404 to avoid leaking existence."""
    scope = customer_scope(user)
    if scope is not None and scope != customer_id:
        raise NotFoundError(f"{entity} not found.")
