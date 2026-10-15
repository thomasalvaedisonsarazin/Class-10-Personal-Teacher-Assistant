"""Shared slowapi rate limiter.

Usage in a router (the endpoint must accept a ``request: Request`` parameter)::

    from app.rate_limit import limiter

    @router.post("/google")
    @limiter.limit("10/minute")
    def google_login(request: Request, ...): ...
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=not settings.is_test,
    # Shared across processes/servers in production; per-process memory in dev/tests.
    storage_uri=settings.REDIS_URL if settings.is_production else "memory://",
)
