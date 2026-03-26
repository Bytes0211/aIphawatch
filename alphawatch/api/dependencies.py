"""FastAPI dependency functions for auth, database, and Redis."""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.database import async_session_factory
from alphawatch.redis import get_redis_pool
from alphawatch.schemas.auth import CurrentUser


def get_current_user(request: Request) -> CurrentUser:
    """Extract the authenticated user from request state.

    Requires TenantMiddleware to have run first.

    Args:
        request: The current HTTP request.

    Returns:
        The authenticated user's context.

    Raises:
        HTTPException: If auth state is missing (middleware bypassed).
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    role = getattr(request.state, "role", None)

    if not all([tenant_id, user_id, role]):
        raise HTTPException(status_code=401, detail="Not authenticated")

    return CurrentUser(tenant_id=tenant_id, user_id=user_id, role=role)


async def get_db(
    user: CurrentUser = Depends(get_current_user),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a tenant-scoped async database session.

    Sets ``app.tenant_id`` on the connection so PostgreSQL RLS
    policies can enforce tenant isolation.

    Args:
        user: The current authenticated user (injected).

    Yields:
        An async SQLAlchemy session with tenant context set.
    """
    async with async_session_factory() as session:
        # Set tenant context for Row-Level Security
        await session.execute(
            text("SET LOCAL app.tenant_id = :tid"),
            {"tid": user.tenant_id},
        )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> aioredis.Redis:
    """Return the shared Redis client.

    Returns:
        The active Redis connection pool client.
    """
    return get_redis_pool()


def require_role(allowed_roles: list[str]):
    """Create a dependency that enforces role-based access control.

    Args:
        allowed_roles: List of roles permitted to access the endpoint.

    Returns:
        A dependency function that validates the user's role.

    Raises:
        HTTPException: If the user's role is not in ``allowed_roles``.
    """

    def _check_role(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' not authorized. "
                f"Required: {', '.join(allowed_roles)}",
            )
        return user

    return _check_role
