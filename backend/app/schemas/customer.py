from typing import Annotated

from pydantic import EmailStr, Field, StringConstraints, field_validator

from app.schemas.auth import _normalize_email
from app.schemas.common import InputModel, LongText, Name, OutputModel

Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=32, pattern=r"^[0-9+()\-\s]*$")
]


class CustomerCreate(InputModel):
    name: Name
    email: EmailStr = Field(max_length=254)
    phone: Phone | None = None
    address: LongText | None = None

    _email = field_validator("email")(_normalize_email)


class CustomerUpdate(InputModel):
    name: Name | None = None
    email: EmailStr | None = Field(default=None, max_length=254)
    phone: Phone | None = None
    address: LongText | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return _normalize_email(value) if value else value


class CustomerOut(OutputModel):
    id: int
    name: str
    email: str
    phone: str | None
    address: str | None
    is_active: bool
    user_id: int | None
