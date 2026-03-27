"""Dashboard repository — aggregates watchlist with financial, sentiment, and brief data."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.models.brief import AnalystBrief
from alphawatch.models.company import Company
from alphawatch.models.document import Document
from alphawatch.models.financial import FinancialSnapshot
from alphawatch.models.risk import RiskFlag
from alphawatch.models.watchlist import WatchlistEntry
from alphawatch.schemas.dashboard import CompanyCard


# Change score weights (tech spec §7.2)
_WEIGHT_FILING = 30
_WEIGHT_RISK = 25
_WEIGHT_PRICE = 2
_WEIGHT_SENTIMENT = 1


def _compute_change_score(
    new_filings: int,
    risk_flags: int,
    price_change_pct: float | None,
    sentiment_delta: int | None,
) -> float:
    """Compute composite change score for dashboard sorting.

    Args:
        new_filings: Count of new filings.
        risk_flags: Count of active risk flags.
        price_change_pct: Price change percentage.
        sentiment_delta: Sentiment score change.

    Returns:
        Weighted change score (higher = more activity).
    """
    return (
        new_filings * _WEIGHT_FILING
        + risk_flags * _WEIGHT_RISK
        + abs(price_change_pct or 0) * _WEIGHT_PRICE
        + abs(sentiment_delta or 0) * _WEIGHT_SENTIMENT
    )


class DashboardRepository:
    """Aggregates watchlist data into dashboard company cards.

    Pulls data from watchlist, financial_snapshots, sentiment_records,
    analyst_briefs, documents, and risk_flags to build a complete
    dashboard view sorted by change_score.

    Args:
        session: An async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_dashboard_cards(
        self,
        user_id: uuid.UUID,
        days: int = 7,
    ) -> list[CompanyCard]:
        """Build dashboard cards for all companies on the user's watchlist.

        For each watched company, aggregates:
        - Latest financial snapshot (price, change %)
        - Sentiment score (7-day average)
        - New filings count (within time window)
        - Risk flag count and max severity
        - Latest brief ID

        Cards are sorted by change_score descending.

        Args:
            user_id: The authenticated user's UUID.
            days: Lookback window for new filings and sentiment.

        Returns:
            List of CompanyCard objects sorted by change_score.
        """
        # Get user's watchlist with companies
        stmt = (
            select(WatchlistEntry, Company)
            .join(Company, Company.id == WatchlistEntry.company_id)
            .where(WatchlistEntry.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        cards: list[CompanyCard] = []
        for entry, company in rows:
            card = await self._build_card(company, user_id, days)
            cards.append(card)

        # Sort by change_score descending
        cards.sort(key=lambda c: c.change_score, reverse=True)
        return cards

    async def _build_card(
        self,
        company: Company,
        user_id: uuid.UUID,
        days: int,
    ) -> CompanyCard:
        """Build a single CompanyCard with aggregated data.

        Args:
            company: The Company ORM object.
            user_id: User UUID for brief lookup.
            days: Lookback window.

        Returns:
            A fully populated CompanyCard.
        """
        company_id = company.id

        # Latest financial snapshot
        snap = await self._get_latest_snapshot(company_id)
        price = float(snap.price) if snap and snap.price else None
        price_change = float(snap.price_change_pct) if snap and snap.price_change_pct else None

        # Sentiment (7-day average via raw SQL for efficiency)
        sentiment = await self._get_avg_sentiment(company_id, days)

        # New filings count
        filings_count = await self._count_new_filings(company_id, days)

        # Risk flags
        risk_count, max_severity = await self._get_risk_summary(company_id)

        # Latest brief
        brief_id = await self._get_latest_brief_id(company_id, user_id)

        # Last updated timestamp
        last_updated = snap.created_at if snap else None

        change_score = _compute_change_score(
            new_filings=filings_count,
            risk_flags=risk_count,
            price_change_pct=price_change,
            sentiment_delta=sentiment,
        )

        return CompanyCard(
            company_id=company_id,
            ticker=company.ticker,
            name=company.name,
            sector=company.sector,
            price=price,
            price_change_pct=price_change,
            sentiment_score=sentiment,
            sentiment_delta=sentiment,  # simplified: delta ≈ score for Phase 1
            new_filings_count=filings_count,
            risk_flag_count=risk_count,
            risk_flag_max_severity=max_severity,
            last_updated_at=last_updated,
            brief_id=brief_id,
            change_score=change_score,
        )

    async def _get_latest_snapshot(
        self, company_id: uuid.UUID
    ) -> FinancialSnapshot | None:
        """Get the most recent financial snapshot."""
        stmt = (
            select(FinancialSnapshot)
            .where(FinancialSnapshot.company_id == company_id)
            .order_by(FinancialSnapshot.snapshot_date.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_avg_sentiment(
        self, company_id: uuid.UUID, days: int
    ) -> int | None:
        """Get average sentiment score over the lookback window."""
        sql = text(
            """
            SELECT AVG(score)::int
            FROM sentiment_records
            WHERE company_id = :cid
              AND scored_at >= NOW() - MAKE_INTERVAL(days => :days)
            """
        )
        result = await self._session.execute(
            sql, {"cid": str(company_id), "days": days}
        )
        return result.scalar_one_or_none()

    async def _count_new_filings(
        self, company_id: uuid.UUID, days: int
    ) -> int:
        """Count documents ingested within the lookback window."""
        sql = text(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE company_id = :cid
              AND ingested_at >= NOW() - MAKE_INTERVAL(days => :days)
            """
        )
        result = await self._session.execute(
            sql, {"cid": str(company_id), "days": days}
        )
        return result.scalar_one() or 0

    async def _get_risk_summary(
        self, company_id: uuid.UUID
    ) -> tuple[int, str | None]:
        """Get risk flag count and highest severity."""
        sql = text(
            """
            SELECT COUNT(*), MAX(
                CASE severity
                    WHEN 'critical' THEN 4
                    WHEN 'high' THEN 3
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 1
                    ELSE 0
                END
            ) AS max_sev_rank
            FROM risk_flags
            WHERE company_id = :cid
            """
        )
        result = await self._session.execute(sql, {"cid": str(company_id)})
        row = result.one()
        count = row[0] or 0
        sev_rank = row[1]

        sev_map = {4: "critical", 3: "high", 2: "medium", 1: "low"}
        max_severity = sev_map.get(sev_rank) if sev_rank else None

        return count, max_severity

    async def _get_latest_brief_id(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> uuid.UUID | None:
        """Get the most recent brief ID for user + company."""
        stmt = (
            select(AnalystBrief.id)
            .where(
                AnalystBrief.company_id == company_id,
                AnalystBrief.user_id == user_id,
            )
            .order_by(AnalystBrief.generated_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
