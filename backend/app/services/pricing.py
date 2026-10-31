"""Pure pricing and billing-calendar helpers (no database access)."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.models.enums import BillingPeriod
from app.utils.money import ZERO, percent_of, round_money


@dataclass(frozen=True)
class LineAmounts:
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal


@dataclass(frozen=True)
class BillableLine:
    product_id: int | None
    variant_id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_name: str | None
    tax_rate: Decimal

    @property
    def subtotal(self) -> Decimal:
        return round_money(self.quantity * self.unit_price)


def compute_line(quantity: Decimal, unit_price: Decimal, tax_rate: Decimal | None) -> LineAmounts:
    rate = tax_rate if tax_rate is not None else ZERO
    subtotal = round_money(quantity * unit_price)
    tax = percent_of(subtotal, rate)
    return LineAmounts(subtotal=subtotal, tax_rate=rate, tax_amount=tax, total=subtotal + tax)


def variant_unit_price(sales_price: Decimal, extra_price: Decimal | None) -> Decimal:
    return round_money(sales_price + (extra_price or ZERO))


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def next_period_start(
    anchor: date, current: date, period: BillingPeriod, interval: int
) -> date:
    """Start of the period after `current`. Monthly/yearly periods are computed from the
    subscription's anchor date so that e.g. a 31 Jan start bills 28 Feb, then 31 Mar."""
    if period == BillingPeriod.DAILY:
        return current + timedelta(days=interval)
    if period == BillingPeriod.WEEKLY:
        return current + timedelta(weeks=interval)
    step = interval if period == BillingPeriod.MONTHLY else 12 * interval
    elapsed = (current.year - anchor.year) * 12 + (current.month - anchor.month)
    return add_months(anchor, elapsed + step)


def compute_expiry(
    start: date, period: BillingPeriod, interval: int, duration_periods: int | None
) -> date | None:
    """Last day (inclusive) covered by a fixed-duration plan; None for open-ended plans."""
    if duration_periods is None:
        return None
    current = start
    for _ in range(duration_periods):
        current = next_period_start(start, current, period, interval)
    return current - timedelta(days=1)


_DAYS_PER_MONTH = Decimal("365.25") / Decimal("12")
_MONTHLY_FACTOR: dict[BillingPeriod, Decimal] = {
    BillingPeriod.DAILY: _DAYS_PER_MONTH,
    BillingPeriod.WEEKLY: _DAYS_PER_MONTH / Decimal("7"),
    BillingPeriod.MONTHLY: Decimal("1"),
    BillingPeriod.YEARLY: Decimal("1") / Decimal("12"),
}


def monthly_equivalent(amount: Decimal, period: BillingPeriod, interval: int) -> Decimal:
    return amount * _MONTHLY_FACTOR[period] / Decimal(interval)
