import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str, *, fields: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.fields = fields or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class BusinessRuleError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "business_rule_violation"


def _error_body(code: str, message: str, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "fields": fields or {}}}


def _field_name(loc: tuple[Any, ...]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "request"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(exc.status_code, _error_body(exc.code, exc.message, exc.fields))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            message = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
            fields.setdefault(_field_name(tuple(err.get("loc", ()))), message)
        return JSONResponse(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            _error_body("validation_error", "Some fields are invalid.", fields),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Integrity error: %s", exc.orig)
        return JSONResponse(
            status.HTTP_409_CONFLICT,
            _error_body("conflict", "The request conflicts with existing data."),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(exc.status_code, _error_body("http_error", str(exc.detail)))

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            _error_body("internal_error", "An unexpected error occurred."),
        )
