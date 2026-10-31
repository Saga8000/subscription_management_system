from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models import Discount, Product, Subscription, User
from app.models.enums import DiscountType
from app.schemas.discount import DiscountCreate, DiscountOut, DiscountUpdate
from app.services import audit_service
from app.services.pricing import BillableLine
from app.utils.money import ZERO, allocate_proportionally, percent_of


def to_out(discount: Discount) -> DiscountOut:
    return DiscountOut.model_validate(
        {
            **{c: getattr(discount, c) for c in DiscountOut.model_fields if hasattr(discount, c)},
            "product_ids": sorted(p.id for p in discount.products),
            "subscription_ids": sorted(s.id for s in discount.subscriptions),
        }
    )


def _load(db: Session, discount_id: int) -> Discount:
    discount = db.scalar(
        select(Discount)
        .where(Discount.id == discount_id)
        .options(selectinload(Discount.products), selectinload(Discount.subscriptions))
    )
    if discount is None:
        raise NotFoundError("Discount not found.")
    return discount


def list_discounts(db: Session) -> list[Discount]:
    return list(
        db.scalars(
            select(Discount)
            .options(selectinload(Discount.products), selectinload(Discount.subscriptions))
            .order_by(Discount.name)
        ).all()
    )


def get_discount(db: Session, discount_id: int) -> Discount:
    return _load(db, discount_id)


def _apply(db: Session, discount: Discount, data: DiscountCreate | DiscountUpdate) -> None:
    products = list(db.scalars(select(Product).where(Product.id.in_(data.product_ids))).all())
    if len(products) != len(set(data.product_ids)):
        raise BusinessRuleError("One or more products do not exist.", fields={"product_ids": "Unknown product"})
    subscriptions = list(
        db.scalars(select(Subscription).where(Subscription.id.in_(data.subscription_ids))).all()
    )
    if len(subscriptions) != len(set(data.subscription_ids)):
        raise BusinessRuleError(
            "One or more subscriptions do not exist.", fields={"subscription_ids": "Unknown subscription"}
        )
    if data.usage_limit is not None and data.usage_limit < discount.usage_count:
        raise BusinessRuleError(
            f"Usage limit cannot be lower than current usage ({discount.usage_count}).",
            fields={"usage_limit": "Below current usage"},
        )
    for field in (
        "name", "discount_type", "value", "min_purchase_amount", "min_quantity",
        "valid_from", "valid_until", "usage_limit", "is_active",
    ):
        setattr(discount, field, getattr(data, field))
    discount.products = products
    discount.subscriptions = subscriptions


def create_discount(db: Session, data: DiscountCreate, actor: User) -> Discount:
    discount = Discount(usage_count=0, created_by_id=actor.id)
    _apply(db, discount, data)
    db.add(discount)
    db.flush()
    audit_service.record(db, actor_id=actor.id, action="discount.create", entity_type="discount", entity_id=discount.id)
    db.commit()
    return _load(db, discount.id)


def update_discount(db: Session, discount_id: int, data: DiscountUpdate, actor: User) -> Discount:
    discount = _load(db, discount_id)
    _apply(db, discount, data)
    audit_service.record(db, actor_id=actor.id, action="discount.update", entity_type="discount", entity_id=discount.id)
    db.commit()
    return _load(db, discount.id)


# --- Invoice-time application -------------------------------------------------------------


def compute_discount_amounts(
    discount: Discount, subscription_id: int, lines: list[BillableLine], on_date: date
) -> list[Decimal] | None:
    """Per-line discount amounts if `discount` applies to these lines, else None."""
    if not discount.is_active:
        return None
    if discount.valid_from and on_date < discount.valid_from:
        return None
    if discount.valid_until and on_date > discount.valid_until:
        return None
    if discount.usage_limit is not None and discount.usage_count >= discount.usage_limit:
        return None
    subscription_ids = {s.id for s in discount.subscriptions}
    if subscription_ids and subscription_id not in subscription_ids:
        return None
    product_ids = {p.id for p in discount.products}
    eligible = [i for i, line in enumerate(lines) if not product_ids or line.product_id in product_ids]
    if not eligible:
        return None
    eligible_qty = sum((lines[i].quantity for i in eligible), ZERO)
    eligible_base = sum((lines[i].subtotal for i in eligible), ZERO)
    if eligible_base <= 0:
        return None
    if discount.min_quantity is not None and eligible_qty < discount.min_quantity:
        return None
    if discount.min_purchase_amount is not None and eligible_base < discount.min_purchase_amount:
        return None

    amounts = [ZERO for _ in lines]
    if discount.discount_type == DiscountType.PERCENTAGE:
        for i in eligible:
            amounts[i] = percent_of(lines[i].subtotal, discount.value)
    else:
        parts = allocate_proportionally(
            min(discount.value, eligible_base), [lines[i].subtotal for i in eligible]
        )
        for i, part in zip(eligible, parts, strict=True):
            amounts[i] = part
    return amounts


def best_discount(
    db: Session, subscription_id: int, lines: list[BillableLine], on_date: date
) -> tuple[Discount, list[Decimal]] | None:
    """Automatically choose the single applicable discount giving the largest reduction
    (ties: lowest id). Discounts are not stacked."""
    candidates = db.scalars(
        select(Discount)
        .where(
            Discount.is_active.is_(True),
            or_(Discount.valid_from.is_(None), Discount.valid_from <= on_date),
            or_(Discount.valid_until.is_(None), Discount.valid_until >= on_date),
            or_(Discount.usage_limit.is_(None), Discount.usage_count < Discount.usage_limit),
        )
        .options(selectinload(Discount.products), selectinload(Discount.subscriptions))
        .order_by(Discount.id)
    ).all()
    best: tuple[Discount, list[Decimal]] | None = None
    best_total = ZERO
    for discount in candidates:
        amounts = compute_discount_amounts(discount, subscription_id, lines, on_date)
        if amounts is None:
            continue
        total = sum(amounts, ZERO)
        if total > best_total:
            best, best_total = (discount, amounts), total
    return best


def consume_usage(db: Session, discount_id: int) -> None:
    """Row-locks the discount so concurrent billing cannot exceed the usage limit."""
    discount = db.execute(
        select(Discount).where(Discount.id == discount_id).with_for_update()
    ).scalar_one()
    if discount.usage_limit is not None and discount.usage_count >= discount.usage_limit:
        raise BusinessRuleError(f"Discount '{discount.name}' has reached its usage limit.")
    discount.usage_count += 1


def release_usage(db: Session, discount_id: int) -> None:
    discount = db.execute(
        select(Discount).where(Discount.id == discount_id).with_for_update()
    ).scalar_one_or_none()
    if discount is not None and discount.usage_count > 0:
        discount.usage_count -= 1
