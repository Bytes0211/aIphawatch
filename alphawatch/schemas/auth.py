"""Auth-related Pydantic schemas."""

from pydantic import BaseModel


class CurrentUser(BaseModel):
    """Authenticated user context extracted from Cognito JWT.

    Attributes:
        user_id: Cognito ``sub`` claim (UUID).
        tenant_id: Custom ``tenant_id`` attribute from Cognito.
        role: Custom ``role`` attribute (admin, analyst, viewer).
    """

    user_id: str
    tenant_id: str
    role: str
