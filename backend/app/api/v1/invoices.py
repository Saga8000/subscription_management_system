from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import customer_scope, require_any_user, require_staff
from app.dependencies import get_db
from app.models import User
from app.models.enums import InvoiceStatus
from app.repositories.invoice_repository import invoice_list_stmt
from app.schemas.invoice import BillingRunRequest, BillingRunResult, InvoiceListItem, InvoiceOut
from app.services import billing_service
from app.services import invoice_service as svc
from app.utils.pagination import Page, PageParams, paginate

router = APIRouter(tags=["invoices"])


@router.get("/invoices", response_model=Page[InvoiceListItem])
def list_invoices(
    status_filter: InvoiceStatus | None = Query(None, alias="status"),
    customer_id: int | None = None,
    subscription_id: int | None = None,
    overdue: bool | None = None,
    q: str | None = Query(None, max_length=50),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_user),
) -> Page[InvoiceListItem]:
    today = date.today()
    stmt = invoice_list_stmt(
        customer_scope=customer_scope(user), today=today, status=status_filter,
        customer_id=customer_id, subscription_id=subscription_id, overdue=overdue, q=q,
    )
    items, total = paginate(db, stmt, params)
    return Page(items=[svc.to_list_item(i, today) for i in items], total=total, page=params.page, page_size=params.page_size)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_any_user)) -> InvoiceOut:
    return svc.to_out(svc.get_invoice(db, invoice_id, user), date.today())


@router.post("/invoices/{invoice_id}/confirm", response_model=InvoiceOut)
def confirm_invoice(invoice_id: int, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> InvoiceOut:
    svc.confirm_invoice(db, invoice_id, actor)
    return svc.to_out(svc.get_invoice(db, invoice_id, actor), date.today())


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice(invoice_id: int, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> InvoiceOut:
    svc.cancel_invoice(db, invoice_id, actor)
    return svc.to_out(svc.get_invoice(db, invoice_id, actor), date.today())


@router.post("/billing/run", response_model=BillingRunResult, tags=["billing"])
def run_billing(data: BillingRunRequest, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> BillingRunResult:
    """Generates invoices for every subscription due on or before `as_of`. Safe to re-run:
    already-billed periods are skipped (row lock + unique index on subscription/period)."""
    return billing_service.run_billing(
        db, as_of=data.as_of or date.today(), actor_id=actor.id, auto_confirm=data.auto_confirm
    )
