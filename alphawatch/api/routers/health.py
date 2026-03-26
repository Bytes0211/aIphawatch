"""Health check endpoint."""

from fastapi import APIRouter

from alphawatch.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status.

    This endpoint is unauthenticated and used by ALB health checks.

    Returns:
        Health status response.
    """
    return HealthResponse(status="ok")
