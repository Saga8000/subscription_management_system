from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.database import get_db
from app.models import User

__all__ = ["get_current_user", "get_db"]


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get(get_settings().auth_cookie_name)
    if token:
        return token
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise AuthenticationError("Not authenticated.")
    payload = decode_access_token(token)
    if payload is None or not str(payload["sub"]).isdigit():
        raise AuthenticationError("Your session is invalid or has expired.")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or user.token_version != payload["ver"]:
        raise AuthenticationError("Your session is invalid or has expired.")
    return user
