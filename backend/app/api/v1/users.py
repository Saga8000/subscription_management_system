from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.permissions import require_admin
from app.dependencies import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import UserOut
from app.schemas.user import StaffCreate, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    role: UserRole | None = None, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> list[UserOut]:
    return [auth_service.user_out(u) for u in auth_service.list_users(db, role)]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    data: StaffCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> UserOut:
    return auth_service.user_out(auth_service.create_staff(db, data, actor))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, data: UserUpdate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> UserOut:
    return auth_service.user_out(auth_service.update_user(db, user_id, data, actor))
