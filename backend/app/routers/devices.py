"""Push device registration endpoints (implemented in Phase 2)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])
