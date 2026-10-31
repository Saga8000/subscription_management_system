from datetime import date
from decimal import Decimal

from pydantic import Field, model_validator

from app.models.enums import QuotationStatus
from app.schemas.common import InputModel, LongText, Money, Name, OutputModel, Quantity


class TemplateLineIn(InputModel):
    product_id: int = Field(gt=0)
    variant_id: int | None = Field(default=None, gt=0)
    quantity: Quantity = Decimal("1")


class TemplateLineOut(OutputModel):
    id: int
    product_id: int
    variant_id: int | None
    quantity: Decimal


class TemplateCreate(InputModel):
    name: Name
    plan_id: int = Field(gt=0)
    validity_days: int = Field(default=30, ge=1, le=365)
    notes: LongText | None = None
    is_active: bool = True
    lines: list[TemplateLineIn] = Field(min_length=1, max_length=50)


class TemplateUpdate(InputModel):
    name: Name | None = None
    plan_id: int | None = Field(default=None, gt=0)
    validity_days: int | None = Field(default=None, ge=1, le=365)
    notes: LongText | None = None
    is_active: bool | None = None
    lines: list[TemplateLineIn] | None = Field(default=None, min_length=1, max_length=50)


class TemplateOut(OutputModel):
    id: int
    name: str
    plan_id: int
    validity_days: int
    notes: str | None
    is_active: bool
    lines: list[TemplateLineOut]


class QuotationLineIn(InputModel):
    product_id: int = Field(gt=0)
    variant_id: int | None = Field(default=None, gt=0)
    quantity: Quantity = Decimal("1")
    # Optional negotiated price; defaults to product price + variant extra.
    unit_price: Money | None = None
    # Defaults to the product's tax when omitted; send `null` together with `no_tax=true` to skip.
    tax_id: int | None = Field(default=None, gt=0)
    no_tax: bool = False


class LineOut(OutputModel):
    id: int
    product_id: int
    variant_id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_id: int | None
    tax_rate: Decimal = Decimal("0")
    subtotal: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class QuotationCreate(InputModel):
    customer_id: int = Field(gt=0)
    plan_id: int | None = Field(default=None, gt=0)
    template_id: int | None = Field(default=None, gt=0)
    start_date: date
    expiration_date: date | None = None
    payment_terms_days: int = Field(default=15, ge=0, le=365)
    notes: LongText | None = None
    lines: list[QuotationLineIn] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _plan_or_template(self) -> "QuotationCreate":
        if self.plan_id is None and self.template_id is None:
            raise ValueError("Either plan_id or template_id is required")
        if not self.lines and self.template_id is None:
            raise ValueError("At least one line is required when no template is used")
        return self


class QuotationUpdate(InputModel):
    plan_id: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    expiration_date: date | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    notes: LongText | None = None
    lines: list[QuotationLineIn] | None = Field(default=None, min_length=1, max_length=50)


class QuotationOut(OutputModel):
    id: int
    number: str
    customer_id: int
    customer_name: str
    plan_id: int
    plan_name: str
    template_id: int | None
    status: QuotationStatus
    quotation_date: date
    expiration_date: date
    start_date: date
    payment_terms_days: int
    notes: str | None
    renewal_of_id: int | None
    subscription_id: int | None
    is_expired: bool
    lines: list[LineOut]
    untaxed_amount: Decimal
    tax_total: Decimal
    total: Decimal


class QuotationListItem(OutputModel):
    id: int
    number: str
    customer_id: int
    customer_name: str
    plan_name: str
    status: QuotationStatus
    quotation_date: date
    expiration_date: date
    start_date: date
    is_expired: bool
