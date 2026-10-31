from pydantic import EmailStr, Field, field_validator

from app.core.security import password_policy_errors
from app.models.enums import UserRole
from app.schemas.common import InputModel, Name, OutputModel


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _check_password(value: str) -> str:
    errors = password_policy_errors(value)
    if errors:
        raise ValueError("Password " + ", ".join(errors) + ".")
    return value


class RegisterRequest(InputModel):
    email: EmailStr = Field(max_length=254)
    full_name: Name
    password: str = Field(max_length=128)

    _email = field_validator("email")(_normalize_email)
    _password = field_validator("password")(_check_password)


class LoginRequest(InputModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    _email = field_validator("email")(_normalize_email)


class ForgotPasswordRequest(InputModel):
    email: EmailStr = Field(max_length=254)

    _email = field_validator("email")(_normalize_email)


class ForgotPasswordResponse(OutputModel):
    message: str
    # Only populated when APP_ENV=development (no email provider is configured).
    dev_reset_token: str | None = None


class ResetPasswordRequest(InputModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(max_length=128)

    _password = field_validator("new_password")(_check_password)


class UserOut(OutputModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    customer_id: int | None = None
