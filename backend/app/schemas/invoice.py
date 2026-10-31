from datetime import date, datetime
from decimal import Decimal

from app.models.enums import InvoiceStatus
from app.schemas.common import InputModel, OutputModel
from app.schemas.payment import PaymentOut


class InvoiceLineOut(OutputModel):
    id: int
    product_id: int | None
    variant_id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_subtotal: Decimal
    discount_amount: Decimal
    tax_name: str | None
    tax_rate: Decimal
    tax_amount: Decimal
    line_total: Decimal


class InvoiceListItem(OutputModel):
    id: int
    number: str
    subscription_id: int
    customer_id: int
    customer_name: str
    status: InvoiceStatus
    invoice_date: date
    due_date: date
    period_start: date
    period_end: date
    total: Decimal
    amount_paid: Decimal
    amount_due: Decimal
    is_overdue: bool


class InvoiceOut(InvoiceListItem):
    subscription_number: str
    customer_email: str
    customer_address: str | None
    subtotal: Decimal
    discount_total: Decimal
    discount_description: str | None
    untaxed_amount: Decimal
    tax_total: Decimal
    confirmed_at: datetime | None
    paid_at: datetime | None
    cancelled_at: datetime | None
    lines: list[InvoiceLineOut]
    payments: list[PaymentOut]


class GenerateInvoiceRequest(InputModel):
    as_of: date | None = None


class BillingRunRequest(InputModel):
    as_of: date | None = None
    auto_confirm: bool = False


class BillingFailure(OutputModel):
    subscription_id: int
    subscription_number: str
    error: str


class BillingRunResult(OutputModel):
    as_of: date
    subscriptions_checked: int
    invoices_created: list[str]
    subscriptions_closed: list[str]
    failures: list[BillingFailure]
