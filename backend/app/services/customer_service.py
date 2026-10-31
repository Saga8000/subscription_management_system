from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.permissions import ensure_can_access_customer
from app.models import Customer, User
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services import audit_service
from app.utils.pagination import PageParams, paginate


def list_customers(
    db: Session, params: PageParams, q: str | None = None, active: bool | None = None
) -> tuple[list[Customer], int]:
    stmt = select(Customer).order_by(Customer.name, Customer.id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Customer.name.ilike(pattern), Customer.email.ilike(pattern)))
    if active is not None:
        stmt = stmt.where(Customer.is_active.is_(active))
    return paginate(db, stmt, params)


def get_customer(db: Session, customer_id: int, user: User) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError("Customer not found.")
    ensure_can_access_customer(user, customer.id, "Customer")
    return customer


def _ensure_email_free(db: Session, email: str, exclude_id: int | None = None) -> None:
    stmt = select(Customer.id).where(Customer.email == email)
    if exclude_id is not None:
        stmt = stmt.where(Customer.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("A customer with this email already exists.", fields={"email": "Already used"})


def create_customer(db: Session, data: CustomerCreate, actor: User) -> Customer:
    _ensure_email_free(db, data.email)
    customer = Customer(**data.model_dump())
    db.add(customer)
    db.flush()
    audit_service.record(db, actor_id=actor.id, action="customer.create", entity_type="customer", entity_id=customer.id)
    db.commit()
    return customer


def update_customer(db: Session, customer_id: int, data: CustomerUpdate, actor: User) -> Customer:
    customer = get_customer(db, customer_id, actor)
    changes = data.model_dump(exclude_unset=True)
    for required in ("name", "email", "is_active"):
        if required in changes and changes[required] is None:
            raise BusinessRuleError(f"{required} cannot be empty.", fields={required: "Required"})
    if "email" in changes:
        _ensure_email_free(db, changes["email"], exclude_id=customer.id)
    for field, value in changes.items():
        setattr(customer, field, value)
    audit_service.record(db, actor_id=actor.id, action="customer.update", entity_type="customer", entity_id=customer.id)
    db.commit()
    return customer
