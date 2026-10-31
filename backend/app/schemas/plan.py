from datetime import date

from pydantic import Field, model_validator

from app.models.enums import BillingPeriod
from app.schemas.common import InputModel, Name, OutputModel


class PlanBase(InputModel):
    name: Name
    billing_period: BillingPeriod
    billing_interval: int = Field(default=1, ge=1, le=36)
    min_quantity: int = Field(default=1, ge=1, le=100_000)
    available_from: date | None = None
    available_until: date | None = None
    duration_periods: int | None = Field(default=None, ge=1, le=1200)
    is_closable: bool = True
    is_pausable: bool = True
    is_renewable: bool = True
    auto_close: bool = True
    is_active: bool = True

    @model_validator(mode="after")
    def _check_availability(self) -> "PlanBase":
        if self.available_from and self.available_until and self.available_until < self.available_from:
            raise ValueError("available_until must be on or after available_from")
        return self


class PlanCreate(PlanBase):
    pass


class PlanUpdate(InputModel):
    name: Name | None = None
    billing_period: BillingPeriod | None = None
    billing_interval: int | None = Field(default=None, ge=1, le=36)
    min_quantity: int | None = Field(default=None, ge=1, le=100_000)
    available_from: date | None = None
    available_until: date | None = None
    duration_periods: int | None = Field(default=None, ge=1, le=1200)
    is_closable: bool | None = None
    is_pausable: bool | None = None
    is_renewable: bool | None = None
    auto_close: bool | None = None
    is_active: bool | None = None


class PlanOut(OutputModel):
    id: int
    name: str
    billing_period: BillingPeriod
    billing_interval: int
    min_quantity: int
    available_from: date | None
    available_until: date | None
    duration_periods: int | None
    is_closable: bool
    is_pausable: bool
    is_renewable: bool
    auto_close: bool
    is_active: bool
