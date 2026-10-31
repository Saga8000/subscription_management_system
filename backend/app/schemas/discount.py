from datetime import date
from decimal import Decimal

from pydantic import Field, model_validator

from app.models.enums import DiscountType
from app.schemas.common import InputModel, Money, Name, OutputModel, PositiveMoney, Quantity


class DiscountBase(InputModel):
    name: Name
    discount_type: DiscountType
    value: PositiveMoney
    min_purchase_amount: Money | None = None
    min_quantity: Quantity | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    usage_limit: int | None = Field(default=None, ge=1, le=1_000_000)
    is_active: bool = True
    product_ids: list[int] = Field(default_factory=list, max_length=200)
    subscription_ids: list[int] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def _validate(self) -> "DiscountBase":
        if self.discount_type == DiscountType.PERCENTAGE and self.value > 100:
            raise ValueError("A percentage discount cannot exceed 100")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until must be on or after valid_from")
        return self


class DiscountCreate(DiscountBase):
    pass


class DiscountUpdate(DiscountBase):
    """Full replacement (PUT semantics) so cross-field rules are always checked together."""


class DiscountOut(OutputModel):
    id: int
    name: str
    discount_type: DiscountType
    value: Decimal
    min_purchase_amount: Decimal | None
    min_quantity: Decimal | None
    valid_from: date | None
    valid_until: date | None
    usage_limit: int | None
    usage_count: int
    is_active: bool
    product_ids: list[int]
    subscription_ids: list[int]
