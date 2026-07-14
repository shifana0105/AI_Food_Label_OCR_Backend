"""Health check endpoint (v1)."""

from fastapi import APIRouter

from app.core.config import settings
from app.models.response import APIResponse, HealthData

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=APIResponse[HealthData])
async def health_check() -> APIResponse[HealthData]:
    """Return the service health status.

    Returns:
        The standard envelope with service name, version, and status.
    """
    return APIResponse(
        message="Service is healthy.",
        data=HealthData(
            status="healthy",
            service=settings.PROJECT_NAME,
            version=settings.VERSION,
        ),
    )
