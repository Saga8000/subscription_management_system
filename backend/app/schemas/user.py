from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.auth import _check_password, _normalize_email
from app.schemas.common import InputModel, Name


class StaffCreate(InputModel):
    email: EmailStr = Field(max_length=254)
    full_name: Name
    password: str = Field(max_length=128)
    role: Literal["staff", "admin"] = "staff"

    _email = field_validator("email")(_normalize_email)
    _password = field_validator("password")(_check_password)


class UserUpdate(InputModel):
    full_name: Name | None = None
    is_active: bool | None = None
