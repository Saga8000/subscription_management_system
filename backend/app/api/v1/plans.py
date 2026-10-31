from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.permissions import is_internal, require_any_user, require_staff
from app.dependencies import get_db
from app.models import User
from app.schemas.plan import PlanCreate, PlanOut, PlanUpdate
from app.services import plan_service

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanOut])
def list_plans(
    active_only: bool = False, db: Session = Depends(get_db), user: User = Depends(require_any_user)
) -> list[PlanOut]:
    plans = plan_service.list_plans(db, active_only=active_only or not is_internal(user))
    return [PlanOut.model_validate(p) for p in plans]


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: int, db: Session = Depends(get_db), _: User = Depends(require_any_user)) -> PlanOut:
    return PlanOut.model_validate(plan_service.get_plan(db, plan_id))


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(data: PlanCreate, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> PlanOut:
    return PlanOut.model_validate(plan_service.create_plan(db, data, actor))


@router.patch("/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: int, data: PlanUpdate, db: Session = Depends(get_db), actor: User = Depends(require_staff)
) -> PlanOut:
    return PlanOut.model_validate(plan_service.update_plan(db, plan_id, data, actor))
