"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from alphawatch.api.middleware import TenantMiddleware
from alphawatch.api.routers import briefs, companies, health, ingestion, watchlist
from alphawatch.config import get_settings
from alphawatch.redis import close_redis, init_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events.

    Initializes Redis pool on startup and closes it on shutdown.
    Database engine is created at module import time via SQLAlchemy.

    Args:
        app: The FastAPI application instance.
    """
    logger.info("Starting AIphaWatch API...")
    await init_redis()
    logger.info("Redis pool initialized")

    yield

    logger.info("Shutting down AIphaWatch API...")
    await close_redis()
    logger.info("Redis pool closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured FastAPI app instance with middleware,
        routers, and lifespan events registered.
    """
    settings = get_settings()

    app = FastAPI(
        title="AIphaWatch API",
        description="AI-powered equity intelligence for buy-side analysts",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware (outermost first)
    app.add_middleware(TenantMiddleware)

    # Routers
    app.include_router(health.router)
    app.include_router(companies.router)
    app.include_router(watchlist.router)
    app.include_router(ingestion.router)
    app.include_router(briefs.router)

    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    return app


app = create_app()
