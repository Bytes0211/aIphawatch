"""Common response schemas used across API endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response model for the health check endpoint.

    Attributes:
        status: Service health status string.
    """

    status: str = "ok"


class ErrorResponse(BaseModel):
    """Standard error response body.

    Attributes:
        detail: Human-readable error description.
    """

    detail: str
