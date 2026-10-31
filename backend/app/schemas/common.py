from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
SignedMoney = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]
Quantity = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


class InputModel(BaseModel):
    """Request bodies reject unknown fields (protects against mass assignment)."""

    model_config = ConfigDict(extra="forbid")


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageOut(BaseModel):
    message: str
