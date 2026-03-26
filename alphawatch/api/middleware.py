"""Tenant context middleware for multi-tenant request isolation."""

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from alphawatch.api.auth import AuthError, extract_bearer_token, verify_cognito_token

logger = logging.getLogger(__name__)

# Paths that bypass authentication
_PUBLIC_PATHS: set[str] = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts Cognito JWT claims and injects tenant context.

    For every authenticated request, this middleware:
    1. Extracts the bearer token from the Authorization header.
    2. Verifies the JWT against Cognito JWKS.
    3. Sets ``tenant_id``, ``user_id``, and ``role`` on ``request.state``.

    Public paths (health, docs) bypass authentication entirely.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request through the auth pipeline.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The HTTP response.
        """
        # Skip auth for public endpoints
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        try:
            token = extract_bearer_token(
                request.headers.get("authorization")
            )
            claims = await verify_cognito_token(token)

            request.state.tenant_id = claims["custom:tenant_id"]
            request.state.user_id = claims["sub"]
            request.state.role = claims["custom:role"]

        except AuthError as exc:
            logger.warning("Auth failed: %s (path=%s)", exc.detail, request.url.path)
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )
        except Exception:
            logger.exception("Unexpected auth error (path=%s)", request.url.path)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal authentication error"},
            )

        return await call_next(request)
