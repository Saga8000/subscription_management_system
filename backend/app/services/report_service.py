"""Dashboard metrics. All figures come from aggregate SQL queries (no per-row Python loops)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Invoice, Payment, Plan, Subscription, SubscriptionLine
from app.models.enums import InvoiceStatus, SubscriptionStatus
from app.schemas.report import DashboardOut, MonthlyPoint, StatusCount
from app.services import payment_service
from app.services.pricing import add_months, monthly_equivalent
from app.utils.money import ZERO, round_money

_BILLED = (InvoiceStatus.CONFIRMED, InvoiceStatus.PAID)


def _money(value: Decimal | None) -> Decimal:
    return round_money(value or ZERO)


def dashboard(db: Session, *, period_start: date, period_end: date, as_of: date) -> DashboardOut:
    active = db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.ACTIVE)
    ) or 0
    collected = db.scalar(
        select(func.sum(Payment.amount)).where(Payment.payment_date.between(period_start, period_end))
    )
    invoiced = db.scalar(
        select(func.sum(Invoice.total)).where(
            Invoice.status.in_(_BILLED), Invoice.invoice_date.between(period_start, period_end)
        )
    )
    outstanding = db.scalar(
        select(func.sum(Invoice.total - Invoice.amount_paid)).where(Invoice.status == InvoiceStatus.CONFIRMED)
    )
    overdue = db.execute(
        select(func.count(), func.sum(Invoice.total - Invoice.amount_paid)).where(
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.due_date < as_of,
            Invoice.amount_paid < Invoice.total,
        )
    ).one()

    mrr = ZERO
    for period, interval, amount in db.execute(
        select(Plan.billing_period, Plan.billing_interval, func.sum(SubscriptionLine.quantity * SubscriptionLine.unit_price))
        .join(Subscription, Subscription.id == SubscriptionLine.subscription_id)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .group_by(Plan.billing_period, Plan.billing_interval)
    ).all():
        mrr += monthly_equivalent(amount or ZERO, period, interval)

    subscription_status = [
        StatusCount(status=status.value, count=count)
        for status, count in db.execute(
            select(Subscription.status, func.count()).group_by(Subscription.status).order_by(Subscription.status)
        ).all()
    ]
    invoice_status = [
        StatusCount(status=status.value, count=count, amount=_money(amount))
        for status, count, amount in db.execute(
            select(Invoice.status, func.count(), func.sum(Invoice.total)).group_by(Invoice.status).order_by(Invoice.status)
        ).all()
    ]

    recent = db.scalars(
        select(Payment).options(selectinload(Payment.invoice)).order_by(Payment.payment_date.desc(), Payment.id.desc()).limit(10)
    ).all()

    return DashboardOut(
        period_start=period_start, period_end=period_end, as_of=as_of,
        active_subscriptions=active, revenue_collected=_money(collected), amount_invoiced=_money(invoiced),
        outstanding_balance=_money(outstanding), overdue_count=overdue[0] or 0, overdue_amount=_money(overdue[1]),
        monthly_recurring_revenue=_money(mrr), subscription_status=subscription_status,
        invoice_status=invoice_status, monthly=monthly_series(db, as_of, months=6),
        recent_payments=[payment_service.to_list_item(p) for p in recent],
    )


def monthly_series(db: Session, as_of: date, months: int) -> list[MonthlyPoint]:
    first = add_months(as_of.replace(day=1), -(months - 1))
    end = add_months(as_of.replace(day=1), 1)
    collected = {
        key: value
        for key, value in db.execute(
            select(func.to_char(Payment.payment_date, "YYYY-MM"), func.sum(Payment.amount))
            .where(Payment.payment_date >= first, Payment.payment_date < end)
            .group_by(func.to_char(Payment.payment_date, "YYYY-MM"))
        ).all()
    }
    invoiced = {
        key: value
        for key, value in db.execute(
            select(func.to_char(Invoice.invoice_date, "YYYY-MM"), func.sum(Invoice.total))
            .where(Invoice.status.in_(_BILLED), Invoice.invoice_date >= first, Invoice.invoice_date < end)
            .group_by(func.to_char(Invoice.invoice_date, "YYYY-MM"))
        ).all()
    }
    points = []
    for offset in range(months):
        key = add_months(first, offset).strftime("%Y-%m")
        points.append(MonthlyPoint(month=key, collected=_money(collected.get(key)), invoiced=_money(invoiced.get(key))))
    return points
