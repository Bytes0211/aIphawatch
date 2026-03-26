"""Financial snapshot repository — upsert and retrieval."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.models.financial import FinancialSnapshot


class FinancialSnapshotRepository:
    """Data access for financial snapshots.

    Snapshots are keyed by (company_id, snapshot_date) for time-series
    storage with upsert semantics.

    Args:
        session: An async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest(
        self, company_id: uuid.UUID
    ) -> FinancialSnapshot | None:
        """Get the most recent snapshot for a company.

        Args:
            company_id: The company UUID.

        Returns:
            The latest FinancialSnapshot if any exist, otherwise None.
        """
        stmt = (
            select(FinancialSnapshot)
            .where(FinancialSnapshot.company_id == company_id)
            .order_by(FinancialSnapshot.snapshot_date.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_date(
        self, company_id: uuid.UUID, snapshot_date: date
    ) -> FinancialSnapshot | None:
        """Get a snapshot for a specific company and date.

        Args:
            company_id: The company UUID.
            snapshot_date: The date to look up.

        Returns:
            The FinancialSnapshot if found, otherwise None.
        """
        stmt = select(FinancialSnapshot).where(
            FinancialSnapshot.company_id == company_id,
            FinancialSnapshot.snapshot_date == snapshot_date,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        company_id: uuid.UUID,
        snapshot_data: dict[str, Any],
    ) -> FinancialSnapshot:
        """Atomically insert or update a financial snapshot.

        Uses PostgreSQL ``INSERT ... ON CONFLICT DO UPDATE`` on the
        ``(company_id, snapshot_date)`` unique constraint for atomicity.
        No read-before-write race condition.

        Args:
            company_id: The company UUID.
            snapshot_data: Dict with snapshot fields from AlphaVantageClient.

        Returns:
            The created or updated FinancialSnapshot.
        """
        values = {
            "company_id": company_id,
            "snapshot_date": snapshot_data["snapshot_date"],
            "price": snapshot_data.get("price"),
            "price_change_pct": snapshot_data.get("price_change_pct"),
            "market_cap": snapshot_data.get("market_cap"),
            "pe_ratio": snapshot_data.get("pe_ratio"),
            "debt_to_equity": snapshot_data.get("debt_to_equity"),
            "analyst_rating": snapshot_data.get("analyst_rating"),
            "raw_data": snapshot_data.get("raw_data", {}),
        }

        update_cols = {
            "price": values["price"],
            "price_change_pct": values["price_change_pct"],
            "market_cap": values["market_cap"],
            "pe_ratio": values["pe_ratio"],
            "debt_to_equity": values["debt_to_equity"],
            "analyst_rating": values["analyst_rating"],
            "raw_data": values["raw_data"],
        }

        stmt = (
            pg_insert(FinancialSnapshot)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_snapshots_company_date",
                set_=update_cols,
            )
            .returning(FinancialSnapshot)
        )

        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def list_for_company(
        self, company_id: uuid.UUID, limit: int = 30
    ) -> list[FinancialSnapshot]:
        """List recent snapshots for a company.

        Args:
            company_id: The company UUID.
            limit: Maximum number of snapshots to return.

        Returns:
            List of snapshots ordered by date descending.
        """
        stmt = (
            select(FinancialSnapshot)
            .where(FinancialSnapshot.company_id == company_id)
            .order_by(FinancialSnapshot.snapshot_date.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
