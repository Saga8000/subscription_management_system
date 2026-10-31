from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.permissions import require_admin, require_staff
from app.dependencies import get_db
from app.models import User
from app.schemas.discount import DiscountCreate, DiscountOut, DiscountUpdate
from app.services import discount_service as svc

router = APIRouter(prefix="/discounts", tags=["discounts"])


@router.get("", response_model=list[DiscountOut])
def list_discounts(db: Session = Depends(get_db), _: User = Depends(require_staff)) -> list[DiscountOut]:
    return [svc.to_out(d) for d in svc.list_discounts(db)]


@router.get("/{discount_id}", response_model=DiscountOut)
def get_discount(discount_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)) -> DiscountOut:
    return svc.to_out(svc.get_discount(db, discount_id))


@router.post("", response_model=DiscountOut, status_code=status.HTTP_201_CREATED)
def create_discount(data: DiscountCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> DiscountOut:
    return svc.to_out(svc.create_discount(db, data, actor))


@router.put("/{discount_id}", response_model=DiscountOut)
def update_discount(
    discount_id: int, data: DiscountUpdate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> DiscountOut:
    return svc.to_out(svc.update_discount(db, discount_id, data, actor))
