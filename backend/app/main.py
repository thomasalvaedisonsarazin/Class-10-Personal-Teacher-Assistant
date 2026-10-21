"""FastAPI application entry point."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

from app.config import settings
from app.exceptions import error_body, register_exception_handlers
from app.rate_limit import limiter
from app.routers import (
    admin,
    auth,
    billing,
    curriculum,
    devices,
    lessons,
    parent,
    partners,
    progress,
    quiz,
)


def configure_logging() -> None:
    """Configure root logging once (idempotent)."""
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # HTTP clients log every request URL at INFO; keep them quiet so no request details
    # (or credentials a provider might expect in a URL) ever reach the logs.
    for noisy in ("httpx", "httpx2", "httpcore", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


configure_logging()
STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger("app")


async def rate_limit_handler(request: Request, exc: Exception) -> Response:
    """Render slowapi rate-limit errors in the standard error envelope."""
    detail = str(getattr(exc, "detail", "")) or "Too many requests"
    return JSONResponse(
        status_code=429,
        content=error_body("rate_limited", f"Rate limit exceeded: {detail}"),
    )


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )

    application.state.limiter = limiter
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)
    application.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    for module in (
        auth,
        curriculum,
        progress,
        lessons,
        quiz,
        admin,
        parent,
        devices,
        billing,
        partners,
    ):
        application.include_router(module.router)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    # Public pages linked from the Google Play listing.
    @application.get("/privacy", include_in_schema=False)
    async def privacy_policy() -> FileResponse:
        """Privacy policy."""
        return FileResponse(STATIC_DIR / "privacy.html", media_type="text/html")

    @application.get("/delete-account", include_in_schema=False)
    async def delete_account_info() -> FileResponse:
        """How to delete an account (Play Store data-deletion link)."""
        return FileResponse(STATIC_DIR / "delete-account.html", media_type="text/html")

    if settings.serve_local_media:
        media_root = settings.media_root
        media_root.mkdir(parents=True, exist_ok=True)
        application.mount("/media", StaticFiles(directory=media_root), name="media")

    logger.info("App started (environment=%s)", settings.ENVIRONMENT)
    return application


app = create_app()
