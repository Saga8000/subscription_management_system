from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.core.permissions import customer_scope, ensure_can_access_customer, is_internal
from app.models import (
    Customer,
    Plan,
    Product,
    Quotation,
    QuotationLine,
    QuotationTemplate,
    QuotationTemplateLine,
    Tax,
    User,
)
from app.models.enums import QuotationStatus
from app.schemas.quotation import (
    LineOut,
    QuotationCreate,
    QuotationLineIn,
    QuotationListItem,
    QuotationOut,
    QuotationUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from app.services import audit_service, subscription_service
from app.services.pricing import compute_line, variant_unit_price
from app.utils.invoice_number import next_document_number
from app.utils.money import ZERO
from app.utils.pagination import PageParams, paginate

DEFAULT_VALIDITY_DAYS = 30


# --- Shared line helpers ------------------------------------------------------------------


def line_out(line: object) -> LineOut:
    tax = getattr(line, "tax")
    amounts = compute_line(line.quantity, line.unit_price, tax.rate_percent if tax else None)  # type: ignore[attr-defined]
    return LineOut(
        id=line.id,  # type: ignore[attr-defined]
        product_id=line.product_id,  # type: ignore[attr-defined]
        variant_id=line.variant_id,  # type: ignore[attr-defined]
        description=line.description,  # type: ignore[attr-defined]
        quantity=line.quantity,  # type: ignore[attr-defined]
        unit_price=line.unit_price,  # type: ignore[attr-defined]
        tax_id=line.tax_id,  # type: ignore[attr-defined]
        tax_rate=amounts.tax_rate,
        subtotal=amounts.subtotal,
        tax_amount=amounts.tax_amount,
        total=amounts.total,
    )


def totals(lines: list[LineOut]) -> tuple[Decimal, Decimal, Decimal]:
    untaxed = sum((line.subtotal for line in lines), ZERO)
    tax = sum((line.tax_amount for line in lines), ZERO)
    return untaxed, tax, untaxed + tax


def check_plan_available(plan: Plan, on_date: date) -> None:
    if not plan.is_active:
        raise BusinessRuleError(f"Plan '{plan.name}' is not active.", fields={"plan_id": "Inactive plan"})
    if plan.available_from and on_date < plan.available_from:
        raise BusinessRuleError(f"Plan '{plan.name}' is available from {plan.available_from}.", fields={"start_date": "Plan not yet available"})
    if plan.available_until and on_date > plan.available_until:
        raise BusinessRuleError(f"Plan '{plan.name}' was available until {plan.available_until}.", fields={"start_date": "Plan no longer available"})


def build_lines(db: Session, plan: Plan, lines_in: list[QuotationLineIn]) -> list[QuotationLine]:
    products = {
        p.id: p
        for p in db.scalars(
            select(Product)
            .where(Product.id.in_({line.product_id for line in lines_in}))
            .options(selectinload(Product.variants), selectinload(Product.tax))
        ).all()
    }
    taxes = {
        t.id: t
        for t in db.scalars(select(Tax).where(Tax.id.in_({l.tax_id for l in lines_in if l.tax_id}))).all()
    }
    result: list[QuotationLine] = []
    for index, line in enumerate(lines_in):
        key = f"lines.{index}"
        product = products.get(line.product_id)
        if product is None or not product.is_active:
            raise BusinessRuleError(f"Line {index + 1}: product not found or inactive.", fields={f"{key}.product_id": "Unavailable"})
        variant = None
        if line.variant_id is not None:
            variant = next((v for v in product.variants if v.id == line.variant_id), None)
            if variant is None or not variant.is_active:
                raise BusinessRuleError(f"Line {index + 1}: variant does not belong to {product.name} or is inactive.", fields={f"{key}.variant_id": "Invalid variant"})
        if line.quantity < plan.min_quantity:
            raise BusinessRuleError(
                f"Line {index + 1}: plan '{plan.name}' requires a minimum quantity of {plan.min_quantity}.",
                fields={f"{key}.quantity": f"Minimum {plan.min_quantity}"},
            )
        if line.no_tax:
            tax = None
        elif line.tax_id is not None:
            tax = taxes.get(line.tax_id)
            if tax is None or not tax.is_active:
                raise BusinessRuleError(f"Line {index + 1}: tax not found or inactive.", fields={f"{key}.tax_id": "Invalid tax"})
        else:
            tax = product.tax if product.tax and product.tax.is_active else None
        unit_price = (
            line.unit_price
            if line.unit_price is not None
            else variant_unit_price(product.sales_price, variant.extra_price if variant else None)
        )
        result.append(
            QuotationLine(
                product_id=product.id,
                variant_id=variant.id if variant else None,
                description=f"{product.name} ({variant.name})" if variant else product.name,
                quantity=line.quantity,
                unit_price=unit_price,
                tax_id=tax.id if tax else None,
            )
        )
    return result


# --- Templates ----------------------------------------------------------------------------


def _load_template(db: Session, template_id: int) -> QuotationTemplate:
    template = db.scalar(
        select(QuotationTemplate)
        .where(QuotationTemplate.id == template_id)
        .options(selectinload(QuotationTemplate.lines))
    )
    if template is None:
        raise NotFoundError("Quotation template not found.")
    return template


def list_templates(db: Session) -> list[QuotationTemplate]:
    return list(
        db.scalars(
            select(QuotationTemplate).options(selectinload(QuotationTemplate.lines)).order_by(QuotationTemplate.name)
        ).all()
    )


def _template_lines(db: Session, plan: Plan, lines: list) -> list[QuotationTemplateLine]:  # type: ignore[type-arg]
    built = build_lines(db, plan, [QuotationLineIn(**l.model_dump()) for l in lines])
    return [QuotationTemplateLine(product_id=b.product_id, variant_id=b.variant_id, quantity=b.quantity) for b in built]


def create_template(db: Session, data: TemplateCreate, actor: User) -> QuotationTemplate:
    plan = db.get(Plan, data.plan_id)
    if plan is None:
        raise BusinessRuleError("Plan not found.", fields={"plan_id": "Unknown plan"})
    template = QuotationTemplate(
        name=data.name, plan_id=plan.id, validity_days=data.validity_days, notes=data.notes,
        is_active=data.is_active, lines=_template_lines(db, plan, data.lines),
    )
    db.add(template)
    db.flush()
    audit_service.record(db, actor_id=actor.id, action="template.create", entity_type="quotation_template", entity_id=template.id)
    db.commit()
    return _load_template(db, template.id)


def update_template(db: Session, template_id: int, data: TemplateUpdate, actor: User) -> QuotationTemplate:
    template = _load_template(db, template_id)
    changes = data.model_dump(exclude_unset=True, exclude={"lines"})
    for field, value in changes.items():
        if value is None and field != "notes":
            raise BusinessRuleError(f"{field} cannot be empty.", fields={field: "Required"})
        setattr(template, field, value)
    plan = db.get(Plan, template.plan_id)
    if plan is None:
        raise BusinessRuleError("Plan not found.", fields={"plan_id": "Unknown plan"})
    if data.lines is not None:
        template.lines = _template_lines(db, plan, data.lines)
    audit_service.record(db, actor_id=actor.id, action="template.update", entity_type="quotation_template", entity_id=template.id)
    db.commit()
    return _load_template(db, template.id)


# --- Quotations ---------------------------------------------------------------------------


def _is_expired(quotation: Quotation, today: date) -> bool:
    return quotation.status in (QuotationStatus.DRAFT, QuotationStatus.SENT) and quotation.expiration_date < today


def to_out(quotation: Quotation) -> QuotationOut:
    lines = [line_out(line) for line in quotation.lines]
    untaxed, tax, total = totals(lines)
    return QuotationOut(
        id=quotation.id, number=quotation.number, customer_id=quotation.customer_id,
        customer_name=quotation.customer.name, plan_id=quotation.plan_id, plan_name=quotation.plan.name,
        template_id=quotation.template_id, status=quotation.status, quotation_date=quotation.quotation_date,
        expiration_date=quotation.expiration_date, start_date=quotation.start_date,
        payment_terms_days=quotation.payment_terms_days, notes=quotation.notes,
        renewal_of_id=quotation.renewal_of_id,
        subscription_id=quotation.subscription.id if quotation.subscription else None,
        is_expired=_is_expired(quotation, date.today()), lines=lines,
        untaxed_amount=untaxed, tax_total=tax, total=total,
    )


def to_list_item(quotation: Quotation) -> QuotationListItem:
    return QuotationListItem(
        id=quotation.id, number=quotation.number, customer_id=quotation.customer_id,
        customer_name=quotation.customer.name, plan_name=quotation.plan.name, status=quotation.status,
        quotation_date=quotation.quotation_date, expiration_date=quotation.expiration_date,
        start_date=quotation.start_date, is_expired=_is_expired(quotation, date.today()),
    )


def _load(db: Session, quotation_id: int, *, lock: bool = False) -> Quotation:
    stmt = select(Quotation).where(Quotation.id == quotation_id)
    if lock:
        stmt = stmt.with_for_update()
    quotation = db.scalar(
        stmt.options(
            selectinload(Quotation.lines).selectinload(QuotationLine.tax),
            selectinload(Quotation.customer),
            selectinload(Quotation.plan),
            selectinload(Quotation.subscription),
        )
    )
    if quotation is None:
        raise NotFoundError("Quotation not found.")
    return quotation


def get_quotation(db: Session, quotation_id: int, user: User) -> Quotation:
    quotation = _load(db, quotation_id)
    ensure_can_access_customer(user, quotation.customer_id, "Quotation")
    if not is_internal(user) and quotation.status == QuotationStatus.DRAFT:
        raise NotFoundError("Quotation not found.")
    return quotation


def list_quotations(
    db: Session, user: User, params: PageParams, status: QuotationStatus | None = None,
    customer_id: int | None = None, q: str | None = None,
) -> tuple[list[Quotation], int]:
    stmt = (
        select(Quotation)
        .options(selectinload(Quotation.customer), selectinload(Quotation.plan))
        .order_by(Quotation.id.desc())
    )
    scope = customer_scope(user)
    if scope is not None:
        stmt = stmt.where(Quotation.customer_id == scope, Quotation.status != QuotationStatus.DRAFT)
    elif customer_id is not None:
        stmt = stmt.where(Quotation.customer_id == customer_id)
    if status is not None:
        stmt = stmt.where(Quotation.status == status)
    if q:
        stmt = stmt.where(Quotation.number.ilike(f"%{q.strip()}%"))
    return paginate(db, stmt, params)


def create_quotation(db: Session, data: QuotationCreate, actor: User) -> Quotation:
    customer = db.get(Customer, data.customer_id)
    if customer is None or not customer.is_active:
        raise BusinessRuleError("Customer not found or inactive.", fields={"customer_id": "Unavailable"})

    validity_days = DEFAULT_VALIDITY_DAYS
    plan_id = data.plan_id
    lines_in = data.lines
    if data.template_id is not None:
        template = _load_template(db, data.template_id)
        if not template.is_active:
            raise BusinessRuleError("This quotation template is inactive.", fields={"template_id": "Inactive"})
        validity_days = template.validity_days
        plan_id = plan_id or template.plan_id
        if not lines_in:
            lines_in = [
                QuotationLineIn(product_id=l.product_id, variant_id=l.variant_id, quantity=l.quantity)
                for l in template.lines
            ]

    plan = db.get(Plan, plan_id)
    if plan is None:
        raise BusinessRuleError("Plan not found.", fields={"plan_id": "Unknown plan"})
    check_plan_available(plan, data.start_date)

    today = date.today()
    expiration = data.expiration_date or today + timedelta(days=validity_days)
    if expiration < today:
        raise BusinessRuleError("Expiration date cannot be in the past.", fields={"expiration_date": "In the past"})

    quotation = Quotation(
        number=next_document_number(db, "quotation"),
        customer_id=customer.id, plan_id=plan.id, template_id=data.template_id,
        status=QuotationStatus.DRAFT, quotation_date=today, expiration_date=expiration,
        start_date=data.start_date, payment_terms_days=data.payment_terms_days, notes=data.notes,
        created_by_id=actor.id, lines=build_lines(db, plan, lines_in),
    )
    db.add(quotation)
    db.flush()
    audit_service.record(db, actor_id=actor.id, action="quotation.create", entity_type="quotation", entity_id=quotation.id)
    db.commit()
    return _load(db, quotation.id)


def update_quotation(db: Session, quotation_id: int, data: QuotationUpdate, actor: User) -> Quotation:
    quotation = _load(db, quotation_id, lock=True)
    if quotation.status != QuotationStatus.DRAFT:
        raise BusinessRuleError("Only draft quotations can be edited.")
    changes = data.model_dump(exclude_unset=True, exclude={"lines"})
    for field in ("plan_id", "start_date", "expiration_date", "payment_terms_days"):
        if field in changes and changes[field] is None:
            raise BusinessRuleError(f"{field} cannot be empty.", fields={field: "Required"})
    for field, value in changes.items():
        setattr(quotation, field, value)
    plan = db.get(Plan, quotation.plan_id)
    if plan is None:
        raise BusinessRuleError("Plan not found.", fields={"plan_id": "Unknown plan"})
    check_plan_available(plan, quotation.start_date)
    if quotation.expiration_date < quotation.quotation_date:
        raise BusinessRuleError("Expiration date must be on or after the quotation date.", fields={"expiration_date": "Too early"})
    if data.lines is not None:
        quotation.lines = build_lines(db, plan, data.lines)
    elif any(line.quantity < plan.min_quantity for line in quotation.lines):
        raise BusinessRuleError(f"Plan '{plan.name}' requires a minimum quantity of {plan.min_quantity} per line.")
    audit_service.record(db, actor_id=actor.id, action="quotation.update", entity_type="quotation", entity_id=quotation.id)
    db.commit()
    db.expire_all()
    return _load(db, quotation.id)


def send_quotation(db: Session, quotation_id: int, actor: User) -> Quotation:
    quotation = _load(db, quotation_id, lock=True)
    if quotation.status != QuotationStatus.DRAFT:
        raise BusinessRuleError(f"Only draft quotations can be sent (current: {quotation.status.value}).")
    if quotation.expiration_date < date.today():
        raise BusinessRuleError("This quotation has expired; update the expiration date first.")
    quotation.status = QuotationStatus.SENT
    audit_service.record(db, actor_id=actor.id, action="quotation.send", entity_type="quotation", entity_id=quotation.id)
    db.commit()
    return _load(db, quotation.id)


def confirm_quotation(db: Session, quotation_id: int, user: User) -> Quotation:
    """Staff confirm, or the customer accepts their own sent quotation. Creates the subscription."""
    quotation = _load(db, quotation_id, lock=True)
    ensure_can_access_customer(user, quotation.customer_id, "Quotation")
    if quotation.status != QuotationStatus.SENT:
        if not is_internal(user) and quotation.status == QuotationStatus.DRAFT:
            raise NotFoundError("Quotation not found.")
        raise BusinessRuleError(
            f"Only sent quotations can be confirmed (current: {quotation.status.value})."
        )
    if quotation.expiration_date < date.today():
        raise BusinessRuleError("This quotation has expired and can no longer be confirmed.")
    check_plan_available(quotation.plan, quotation.start_date)
    quotation.status = QuotationStatus.CONFIRMED
    subscription_service.create_from_quotation(db, quotation, actor_id=user.id)
    audit_service.record(db, actor_id=user.id, action="quotation.confirm", entity_type="quotation", entity_id=quotation.id)
    db.commit()
    db.expire_all()
    return _load(db, quotation.id)


def cancel_quotation(db: Session, quotation_id: int, user: User) -> Quotation:
    quotation = _load(db, quotation_id, lock=True)
    ensure_can_access_customer(user, quotation.customer_id, "Quotation")
    allowed = (
        (QuotationStatus.DRAFT, QuotationStatus.SENT) if is_internal(user) else (QuotationStatus.SENT,)
    )
    if quotation.status not in allowed:
        if not is_internal(user) and quotation.status == QuotationStatus.DRAFT:
            raise NotFoundError("Quotation not found.")
        if not is_internal(user):
            raise PermissionDeniedError("You can only decline quotations that were sent to you.")
        raise BusinessRuleError(f"A {quotation.status.value} quotation cannot be cancelled.")
    quotation.status = QuotationStatus.CANCELLED
    audit_service.record(db, actor_id=user.id, action="quotation.cancel", entity_type="quotation", entity_id=quotation.id)
    db.commit()
    return _load(db, quotation.id)
