"""Dashboard endpoint — watchlist digest sorted by change score."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.api.dependencies import get_current_user, get_db
from alphawatch.repositories.dashboard import DashboardRepository
from alphawatch.schemas.auth import CurrentUser
from alphawatch.schemas.dashboard import DashboardResponse

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    time_range: str = Query("7d", description="Lookback period: 24h, 7d, or 30d"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Get the watchlist dashboard digest.

    Returns a prioritized list of watched companies sorted by
    composite change_score (filings × 30 + risk_flags × 25 +
    |price_change| × 2 + |sentiment_delta| × 1).

    Args:
        time_range: Lookback period for activity detection.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        Dashboard with sorted company cards.
    """
    days_map = {"24h": 1, "7d": 7, "30d": 30}
    days = days_map.get(time_range, 7)

    repo = DashboardRepository(db)
    cards = await repo.get_dashboard_cards(
        user_id=uuid.UUID(user.user_id),
        days=days,
    )

    return DashboardResponse(
        cards=cards,
        as_of=datetime.now(timezone.utc),
        time_range=time_range,
        total=len(cards),
    )
