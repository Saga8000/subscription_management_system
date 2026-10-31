from fastapi import APIRouter, Depends, Query, status
from pydantic import field_validator
from sqlalchemy.orm import Session

from app.core.permissions import require_any_user, require_staff
from app.dependencies import get_db
from app.models import User
from app.schemas.auth import UserOut, _check_password
from app.schemas.common import InputModel
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate
from app.services import auth_service, customer_service
from app.utils.pagination import Page, PageParams

router = APIRouter(prefix="/customers", tags=["customers"])


class PortalAccessRequest(InputModel):
    password: str

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        return _check_password(value)


@router.get("", response_model=Page[CustomerOut])
def list_customers(
    q: str | None = Query(None, max_length=100),
    active: bool | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
) -> Page[CustomerOut]:
    items, total = customer_service.list_customers(db, params, q=q, active=active)
    return Page(items=[CustomerOut.model_validate(c) for c in items], total=total, page=params.page, page_size=params.page_size)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int, db: Session = Depends(get_db), user: User = Depends(require_any_user)
) -> CustomerOut:
    return CustomerOut.model_validate(customer_service.get_customer(db, customer_id, user))


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    data: CustomerCreate, db: Session = Depends(get_db), actor: User = Depends(require_staff)
) -> CustomerOut:
    return CustomerOut.model_validate(customer_service.create_customer(db, data, actor))


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int, data: CustomerUpdate, db: Session = Depends(get_db), actor: User = Depends(require_staff)
) -> CustomerOut:
    return CustomerOut.model_validate(customer_service.update_customer(db, customer_id, data, actor))


@router.post("/{customer_id}/portal-access", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def enable_portal_access(
    customer_id: int, data: PortalAccessRequest, db: Session = Depends(get_db), actor: User = Depends(require_staff)
) -> UserOut:
    return auth_service.user_out(auth_service.enable_portal_access(db, customer_id, data.password, actor))
