from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_any_user, require_staff
from app.dependencies import get_db
from app.models import User
from app.models.enums import QuotationStatus
from app.schemas.quotation import (
    QuotationCreate,
    QuotationListItem,
    QuotationOut,
    QuotationUpdate,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
)
from app.services import quotation_service as svc
from app.utils.pagination import Page, PageParams

router = APIRouter()


@router.get("/quotation-templates", response_model=list[TemplateOut], tags=["quotation templates"])
def list_templates(db: Session = Depends(get_db), _: User = Depends(require_staff)) -> list[TemplateOut]:
    return [TemplateOut.model_validate(t) for t in svc.list_templates(db)]


@router.post("/quotation-templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED, tags=["quotation templates"])
def create_template(data: TemplateCreate, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> TemplateOut:
    return TemplateOut.model_validate(svc.create_template(db, data, actor))


@router.patch("/quotation-templates/{template_id}", response_model=TemplateOut, tags=["quotation templates"])
def update_template(
    template_id: int, data: TemplateUpdate, db: Session = Depends(get_db), actor: User = Depends(require_staff)
) -> TemplateOut:
    return TemplateOut.model_validate(svc.update_template(db, template_id, data, actor))


@router.get("/quotations", response_model=Page[QuotationListItem], tags=["quotations"])
def list_quotations(
    status_filter: QuotationStatus | None = Query(None, alias="status"),
    customer_id: int | None = None,
    q: str | None = Query(None, max_length=50),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_user),
) -> Page[QuotationListItem]:
    items, total = svc.list_quotations(db, user, params, status=status_filter, customer_id=customer_id, q=q)
    return Page(items=[svc.to_list_item(x) for x in items], total=total, page=params.page, page_size=params.page_size)


@router.get("/quotations/{quotation_id}", response_model=QuotationOut, tags=["quotations"])
def get_quotation(quotation_id: int, db: Session = Depends(get_db), user: User = Depends(require_any_user)) -> QuotationOut:
    return svc.to_out(svc.get_quotation(db, quotation_id, user))


@router.post("/quotations", response_model=QuotationOut, status_code=status.HTTP_201_CREATED, tags=["quotations"])
def create_quotation(data: QuotationCreate, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> QuotationOut:
    return svc.to_out(svc.create_quotation(db, data, actor))


@router.patch("/quotations/{quotation_id}", response_model=QuotationOut, tags=["quotations"])
def update_quotation(
    quotation_id: int, data: QuotationUpdate, db: Session = Depends(get_db), actor: User = Depends(require_staff)
) -> QuotationOut:
    return svc.to_out(svc.update_quotation(db, quotation_id, data, actor))


@router.post("/quotations/{quotation_id}/send", response_model=QuotationOut, tags=["quotations"])
def send_quotation(quotation_id: int, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> QuotationOut:
    return svc.to_out(svc.send_quotation(db, quotation_id, actor))


@router.post("/quotations/{quotation_id}/confirm", response_model=QuotationOut, tags=["quotations"])
def confirm_quotation(quotation_id: int, db: Session = Depends(get_db), user: User = Depends(require_any_user)) -> QuotationOut:
    return svc.to_out(svc.confirm_quotation(db, quotation_id, user))


@router.post("/quotations/{quotation_id}/cancel", response_model=QuotationOut, tags=["quotations"])
def cancel_quotation(quotation_id: int, db: Session = Depends(get_db), user: User = Depends(require_any_user)) -> QuotationOut:
    return svc.to_out(svc.cancel_quotation(db, quotation_id, user))
