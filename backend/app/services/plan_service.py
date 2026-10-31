from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models import Plan, Subscription, User
from app.models.enums import SubscriptionStatus
from app.schemas.plan import PlanCreate, PlanUpdate
from app.services import audit_service

_CADENCE_FIELDS = {"billing_period", "billing_interval"}
_REQUIRED = {
    "name", "billing_period", "billing_interval", "min_quantity",
    "is_closable", "is_pausable", "is_renewable", "auto_close", "is_active",
}


def list_plans(db: Session, active_only: bool = False) -> list[Plan]:
    stmt = select(Plan).order_by(Plan.name)
    if active_only:
        stmt = stmt.where(Plan.is_active.is_(True))
    return list(db.scalars(stmt).all())


def get_plan(db: Session, plan_id: int) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.")
    return plan


def create_plan(db: Session, data: PlanCreate, actor: User) -> Plan:
    plan = Plan(**data.model_dump())
    db.add(plan)
    db.flush()
    audit_service.record(db, actor_id=actor.id, action="plan.create", entity_type="plan", entity_id=plan.id)
    db.commit()
    return plan


def update_plan(db: Session, plan_id: int, data: PlanUpdate, actor: User) -> Plan:
    plan = get_plan(db, plan_id)
    changes = data.model_dump(exclude_unset=True)
    for field in _REQUIRED & changes.keys():
        if changes[field] is None:
            raise BusinessRuleError(f"{field} cannot be empty.", fields={field: "Required"})
    cadence_changed = any(
        field in changes and changes[field] != getattr(plan, field) for field in _CADENCE_FIELDS
    )
    if cadence_changed:
        in_use = db.scalar(
            select(Subscription.id).where(
                Subscription.plan_id == plan.id, Subscription.status != SubscriptionStatus.CLOSED
            ).limit(1)
        )
        if in_use is not None:
            raise BusinessRuleError(
                "Billing cadence cannot change while open subscriptions use this plan. Create a new plan instead."
            )
    for field, value in changes.items():
        setattr(plan, field, value)
    if plan.available_from and plan.available_until and plan.available_until < plan.available_from:
        raise BusinessRuleError("available_until must be on or after available_from.", fields={"available_until": "Invalid range"})
    audit_service.record(db, actor_id=actor.id, action="plan.update", entity_type="plan", entity_id=plan.id)
    db.commit()
    return plan
