"""Watchlist repository — user-scoped CRUD."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from alphawatch.models.watchlist import WatchlistEntry


class WatchlistRepository:
    """Data access for the user's watchlist.

    All queries are scoped to a specific user_id. RLS provides
    defense-in-depth tenant isolation.

    Args:
        session: An async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[WatchlistEntry]:
        """List all watchlist entries for a user, eager-loading company.

        Args:
            user_id: The authenticated user's UUID.

        Returns:
            List of WatchlistEntry objects with company relationship loaded.
        """
        stmt = (
            select(WatchlistEntry)
            .options(joinedload(WatchlistEntry.company))
            .where(WatchlistEntry.user_id == user_id)
            .order_by(WatchlistEntry.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_entry(
        self, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> WatchlistEntry | None:
        """Check if a company is already on the user's watchlist.

        Args:
            user_id: The authenticated user's UUID.
            company_id: The company UUID to check.

        Returns:
            The WatchlistEntry if found, otherwise None.
        """
        stmt = select(WatchlistEntry).where(
            WatchlistEntry.user_id == user_id,
            WatchlistEntry.company_id == company_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, user_id: uuid.UUID, company_id: uuid.UUID) -> WatchlistEntry:
        """Add a company to the user's watchlist.

        Args:
            user_id: The authenticated user's UUID.
            company_id: The company UUID to add.

        Returns:
            The newly created WatchlistEntry.
        """
        entry = WatchlistEntry(user_id=user_id, company_id=company_id)
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def remove(self, user_id: uuid.UUID, company_id: uuid.UUID) -> bool:
        """Remove a company from the user's watchlist.

        Args:
            user_id: The authenticated user's UUID.
            company_id: The company UUID to remove.

        Returns:
            True if a row was deleted, False if not found.
        """
        stmt = delete(WatchlistEntry).where(
            WatchlistEntry.user_id == user_id,
            WatchlistEntry.company_id == company_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
