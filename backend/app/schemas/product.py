from decimal import Decimal
from typing import Annotated

from pydantic import Field, StringConstraints

from app.models.enums import ProductType
from app.schemas.common import InputModel, LongText, Money, Name, OutputModel, SignedMoney

Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=6, decimal_places=3)]
VariantName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class TaxCreate(InputModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    rate_percent: Percent
    is_active: bool = True


class TaxUpdate(InputModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None = None
    rate_percent: Percent | None = None
    is_active: bool | None = None


class TaxOut(OutputModel):
    id: int
    name: str
    rate_percent: Decimal
    is_active: bool


class VariantCreate(InputModel):
    name: VariantName
    extra_price: SignedMoney = Decimal("0")
    is_active: bool = True


class VariantUpdate(InputModel):
    name: VariantName | None = None
    extra_price: SignedMoney | None = None
    is_active: bool | None = None


class VariantOut(OutputModel):
    id: int
    name: str
    extra_price: Decimal
    unit_price: Decimal
    is_active: bool


class ProductCreate(InputModel):
    name: Name
    product_type: ProductType = ProductType.SERVICE
    sales_price: Money
    cost_price: Money = Decimal("0")
    notes: LongText | None = None
    tax_id: int | None = Field(default=None, gt=0)
    is_active: bool = True
    variants: list[VariantCreate] = Field(default_factory=list, max_length=50)


class ProductUpdate(InputModel):
    name: Name | None = None
    product_type: ProductType | None = None
    sales_price: Money | None = None
    cost_price: Money | None = None
    notes: LongText | None = None
    tax_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ProductOut(OutputModel):
    id: int
    name: str
    product_type: ProductType
    sales_price: Decimal
    cost_price: Decimal
    notes: str | None
    tax_id: int | None
    tax: TaxOut | None
    is_active: bool
    variants: list[VariantOut]
