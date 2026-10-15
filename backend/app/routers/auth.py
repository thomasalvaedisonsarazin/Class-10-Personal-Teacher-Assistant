"""Authentication (Google Sign-In, dev login, refresh, me) endpoints (implemented in Phase 2)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
