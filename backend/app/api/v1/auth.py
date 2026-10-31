from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import create_access_token
from app.dependencies import get_current_user, get_db
from app.models import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
)
from app.schemas.common import MessageOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_access_token(user.id, user.role.value, user.token_version),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = auth_service.register_customer(db, data)
    _set_session_cookie(response, user)
    return auth_service.user_out(user)


@router.post("/login", response_model=UserOut)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = auth_service.authenticate(db, data)
    _set_session_cookie(response, user)
    return auth_service.user_out(user)


@router.post("/logout", response_model=MessageOut)
def logout(
    response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MessageOut:
    auth_service.logout(db, user)
    response.delete_cookie(get_settings().auth_cookie_name, path="/")
    return MessageOut(message="Logged out.")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return auth_service.user_out(user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    raw = auth_service.request_password_reset(db, data.email)
    message = "If an account exists for this email, a reset link has been generated."
    # No email provider is configured: in development only, the token is returned directly.
    dev_token = raw if get_settings().is_development else None
    return ForgotPasswordResponse(message=message, dev_reset_token=dev_token)


@router.post("/reset-password", response_model=MessageOut)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageOut:
    auth_service.reset_password(db, data.token, data.new_password)
    return MessageOut(message="Password updated. Please sign in.")
