"""Watchlist CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.api.dependencies import get_current_user, get_db
from alphawatch.repositories.companies import CompanyRepository
from alphawatch.repositories.watchlist import WatchlistRepository
from alphawatch.schemas.auth import CurrentUser
from alphawatch.schemas.company import CompanyResponse
from alphawatch.schemas.watchlist import (
    WatchlistAddRequest,
    WatchlistEntryResponse,
    WatchlistResponse,
)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=WatchlistResponse)
async def list_watchlist(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchlistResponse:
    """List all companies on the authenticated user's watchlist.

    Args:
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        The user's watchlist entries with company data.
    """
    repo = WatchlistRepository(db)
    entries = await repo.list_for_user(user.user_id)
    return WatchlistResponse(
        entries=[
            WatchlistEntryResponse(
                id=e.id,
                company=CompanyResponse.model_validate(e.company),
                created_at=e.created_at,
            )
            for e in entries
        ],
        count=len(entries),
    )


@router.post("", response_model=WatchlistEntryResponse, status_code=201)
async def add_to_watchlist(
    body: WatchlistAddRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchlistEntryResponse:
    """Add a company to the user's watchlist by ticker.

    Resolves the ticker to a company. If the company doesn't exist
    in the database, returns 404. If already on the watchlist, returns 409.

    Args:
        body: Request body with ticker to add.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        The newly created watchlist entry.

    Raises:
        HTTPException: 404 if ticker not found, 409 if already on watchlist.
    """
    company_repo = CompanyRepository(db)
    company = await company_repo.get_by_ticker(body.ticker)
    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"Company with ticker '{body.ticker.upper()}' not found",
        )

    watchlist_repo = WatchlistRepository(db)
    existing = await watchlist_repo.get_entry(user.user_id, company.id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"{company.ticker} is already on your watchlist",
        )

    entry = await watchlist_repo.add(user.user_id, company.id)
    return WatchlistEntryResponse(
        id=entry.id,
        company=CompanyResponse.model_validate(company),
        created_at=entry.created_at,
    )


@router.delete("/{company_id}", status_code=204)
async def remove_from_watchlist(
    company_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a company from the user's watchlist.

    Args:
        company_id: The company UUID to remove.
        user: The authenticated user (injected).
        db: Database session (injected).

    Raises:
        HTTPException: 404 if the company was not on the watchlist.
    """
    repo = WatchlistRepository(db)
    removed = await repo.remove(user.user_id, company_id)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail="Company not found on your watchlist",
        )
