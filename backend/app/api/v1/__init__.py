"""Version 1 API router.

Aggregates every v1 endpoint under the ``/api/v1`` prefix. New API
versions get their own package (e.g. ``app.api.v2``) with an
equivalent aggregate router.
"""

from fastapi import APIRouter

from app.api.v1 import health, upload

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(upload.router)
