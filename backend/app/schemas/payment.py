from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field, StringConstraints

from app.models.enums import PaymentMethod
from app.schemas.common import InputModel, LongText, OutputModel, PositiveMoney


class PaymentCreate(InputModel):
    invoice_id: int = Field(gt=0)
    amount: PositiveMoney
    method: PaymentMethod
    payment_date: date
    reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    note: LongText | None = None


class PaymentOut(OutputModel):
    id: int
    invoice_id: int
    amount: Decimal
    method: PaymentMethod
    payment_date: date
    reference: str | None
    note: str | None
    created_at: datetime


class PaymentListItem(PaymentOut):
    invoice_number: str
    customer_name: str
