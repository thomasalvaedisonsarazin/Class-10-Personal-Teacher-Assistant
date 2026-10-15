"""Application exception hierarchy and FastAPI exception handlers.

Every error response uses the envelope ``{"error": {"code": str, "message": str}}``
(validation errors additionally include ``details``).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, client-facing application errors."""

    status_code: int = 400
    code: str = "app_error"
    message: str = "Application error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.headers = headers
        super().__init__(self.message)


class BadRequestError(AppError):
    """400 Bad Request."""

    status_code = 400
    code = "bad_request"
    message = "Bad request"


class UnauthorizedError(AppError):
    """401 Unauthorized (missing/invalid credentials)."""

    status_code = 401
    code = "unauthorized"
    message = "Not authenticated"


class ForbiddenError(AppError):
    """403 Forbidden."""

    status_code = 403
    code = "forbidden"
    message = "You do not have access to this resource"


class NotFoundError(AppError):
    """404 Not Found."""

    status_code = 404
    code = "not_found"
    message = "Resource not found"


class ConflictError(AppError):
    """409 Conflict."""

    status_code = 409
    code = "conflict"
    message = "Conflict"


class RateLimitedError(AppError):
    """429 Too Many Requests."""

    status_code = 429
    code = "rate_limited"
    message = "Too many requests, please try again later"


def error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Build the standard error envelope."""
    return {"error": {"code": code, "message": message, **extra}}


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render an :class:`AppError` as the standard envelope."""
    assert isinstance(exc, AppError)  # noqa: S101 - handler registration guarantees type
    headers = exc.headers or {}
    if exc.status_code == 401:
        headers = {"WWW-Authenticate": "Bearer", **headers}
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message),
        headers=headers or None,
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render request validation errors as the standard envelope with details."""
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    details = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
    return JSONResponse(
        status_code=422,
        content=error_body("validation_error", "Request validation failed", details=details),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render Starlette/FastAPI HTTPExceptions (e.g. 404 route, 405) in the envelope."""
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        429: "rate_limited",
    }
    code = code_map.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, message),
        headers=getattr(exc, "headers", None),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected errors and return a generic 500 envelope."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_body("internal_error", "An unexpected error occurred"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
