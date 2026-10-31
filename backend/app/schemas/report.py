from datetime import date
from decimal import Decimal

from app.schemas.common import OutputModel
from app.schemas.payment import PaymentListItem


class StatusCount(OutputModel):
    status: str
    count: int
    amount: Decimal | None = None


class MonthlyPoint(OutputModel):
    month: str  # YYYY-MM
    collected: Decimal
    invoiced: Decimal


class DashboardOut(OutputModel):
    period_start: date
    period_end: date
    as_of: date
    active_subscriptions: int
    # Cash actually received (payments.payment_date within the period).
    revenue_collected: Decimal
    # Value of confirmed/paid invoices issued in the period (invoice_date within the period).
    amount_invoiced: Decimal
    # Sum of (total - amount_paid) over confirmed invoices, as of now.
    outstanding_balance: Decimal
    # Confirmed invoices with due_date < as_of and a remaining balance.
    overdue_count: int
    overdue_amount: Decimal
    # Estimate: active subscriptions' recurring untaxed amount normalised to one month.
    monthly_recurring_revenue: Decimal
    subscription_status: list[StatusCount]
    invoice_status: list[StatusCount]
    monthly: list[MonthlyPoint]
    recent_payments: list[PaymentListItem]
