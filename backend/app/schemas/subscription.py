from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import StringConstraints

from app.models.enums import BillingPeriod, SubscriptionStatus
from app.schemas.common import InputModel, OutputModel
from app.schemas.quotation import LineOut


class CloseRequest(InputModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None


class SubscriptionListItem(OutputModel):
    id: int
    number: str
    customer_id: int
    customer_name: str
    plan_name: str
    status: SubscriptionStatus
    start_date: date
    expiry_date: date | None
    next_invoice_date: date
    recurring_total: Decimal


class SubscriptionOut(OutputModel):
    id: int
    number: str
    customer_id: int
    customer_name: str
    plan_id: int
    plan_name: str
    billing_period: BillingPeriod
    billing_interval: int
    is_closable: bool
    is_pausable: bool
    is_renewable: bool
    quotation_id: int
    quotation_number: str
    status: SubscriptionStatus
    start_date: date
    expiry_date: date | None
    next_invoice_date: date
    payment_terms_days: int
    activated_at: datetime | None
    paused_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None
    lines: list[LineOut]
    untaxed_amount: Decimal
    tax_total: Decimal
    recurring_total: Decimal
