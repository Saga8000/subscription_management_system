from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.permissions import customer_scope, require_any_user, require_staff
from app.dependencies import get_db
from app.models import User
from app.repositories.invoice_repository import payment_list_stmt
from app.schemas.payment import PaymentCreate, PaymentListItem
from app.services import payment_service
from app.utils.pagination import Page, PageParams, paginate

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("", response_model=Page[PaymentListItem])
def list_payments(
    invoice_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_user),
) -> Page[PaymentListItem]:
    stmt = payment_list_stmt(customer_scope=customer_scope(user), invoice_id=invoice_id, date_from=date_from, date_to=date_to)
    items, total = paginate(db, stmt, params)
    return Page(items=[payment_service.to_list_item(p) for p in items], total=total, page=params.page, page_size=params.page_size)


@router.post("", response_model=PaymentListItem, status_code=status.HTTP_201_CREATED)
def record_payment(data: PaymentCreate, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> PaymentListItem:
    return payment_service.to_list_item(payment_service.record_payment(db, data, actor))
