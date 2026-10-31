from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import require_any_user, require_staff
from app.dependencies import get_db
from app.models import User
from app.models.enums import SubscriptionStatus
from app.schemas.invoice import GenerateInvoiceRequest, InvoiceOut
from app.schemas.quotation import QuotationOut
from app.schemas.subscription import CloseRequest, SubscriptionListItem, SubscriptionOut
from app.services import billing_service, invoice_service, quotation_service
from app.services import subscription_service as svc
from app.utils.pagination import Page, PageParams

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=Page[SubscriptionListItem])
def list_subscriptions(
    status_filter: SubscriptionStatus | None = Query(None, alias="status"),
    customer_id: int | None = None,
    plan_id: int | None = None,
    q: str | None = Query(None, max_length=50),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_user),
) -> Page[SubscriptionListItem]:
    items, total = svc.list_subscriptions(
        db, user, params, status=status_filter, customer_id=customer_id, plan_id=plan_id, q=q
    )
    return Page(items=[svc.to_list_item(s) for s in items], total=total, page=params.page, page_size=params.page_size)


@router.get("/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(subscription_id: int, db: Session = Depends(get_db), user: User = Depends(require_any_user)) -> SubscriptionOut:
    return svc.to_out(svc.get_subscription(db, subscription_id, user))


@router.post("/{subscription_id}/activate", response_model=SubscriptionOut)
def activate(subscription_id: int, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> SubscriptionOut:
    return svc.to_out(svc.activate(db, subscription_id, actor))


@router.post("/{subscription_id}/pause", response_model=SubscriptionOut)
def pause(subscription_id: int, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> SubscriptionOut:
    return svc.to_out(svc.pause(db, subscription_id, actor))


@router.post("/{subscription_id}/resume", response_model=SubscriptionOut)
def resume(subscription_id: int, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> SubscriptionOut:
    return svc.to_out(svc.resume(db, subscription_id, actor))


@router.post("/{subscription_id}/close", response_model=SubscriptionOut)
def close(
    subscription_id: int, data: CloseRequest, db: Session = Depends(get_db), user: User = Depends(require_any_user)
) -> SubscriptionOut:
    return svc.to_out(svc.close(db, subscription_id, user, data.reason))


@router.post("/{subscription_id}/renew", response_model=QuotationOut)
def renew(subscription_id: int, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> QuotationOut:
    quotation = svc.renew(db, subscription_id, actor)
    return quotation_service.to_out(quotation_service.get_quotation(db, quotation.id, actor))


@router.post("/{subscription_id}/generate-invoice", response_model=list[InvoiceOut])
def generate_invoice(
    subscription_id: int, data: GenerateInvoiceRequest,
    db: Session = Depends(get_db), actor: User = Depends(require_staff),
) -> list[InvoiceOut]:
    today = date.today()
    invoices = billing_service.generate_now(db, subscription_id, as_of=data.as_of or today, actor=actor)
    return [invoice_service.to_out(invoice_service.get_invoice(db, i.id, actor), today) for i in invoices]
