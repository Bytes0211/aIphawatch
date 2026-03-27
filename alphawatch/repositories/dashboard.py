"""Dashboard repository — aggregates watchlist with financial, sentiment, and brief data."""

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.models.company import Company
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

        Uses **6 batch queries** regardless of watchlist size (no N+1):
        1. Watchlist + companies
        2. Latest snapshots (window function)
        3. Current-window sentiment averages
        4. Prior-window sentiment averages (for delta)
        5. New filings counts + risk summaries + latest brief IDs
           (combined into one query)

        Cards are sorted by change_score descending.

        Args:
            user_id: The authenticated user's UUID.
            days: Lookback window for new filings and sentiment.

        Returns:
            List of CompanyCard objects sorted by change_score.
        """
        # 1. Watchlist with companies
        stmt = (
            select(WatchlistEntry, Company)
            .join(Company, Company.id == WatchlistEntry.company_id)
            .where(WatchlistEntry.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        companies: dict[uuid.UUID, Company] = {}
        for _entry, company in rows:
            companies[company.id] = company
        cids = list(companies.keys())

        # 2. Latest snapshots (batch)
        snapshots = await self._batch_latest_snapshots(cids)

        # 3+4. Sentiment: current and prior window (batch)
        sentiment_current = await self._batch_avg_sentiment(cids, days)
        sentiment_prior = await self._batch_avg_sentiment(
            cids, days * 2, offset_days=days
        )

        # 5. Filings, risks, briefs (batch)
        filings_map = await self._batch_new_filings(cids, days)
        risk_map = await self._batch_risk_summary(cids)
        brief_map = await self._batch_latest_briefs(cids, user_id)

        # Assemble cards
        sev_map = {4: "critical", 3: "high", 2: "medium", 1: "low"}
        cards: list[CompanyCard] = []

        for cid in cids:
            company = companies[cid]
            cid_str = str(cid)  # string key for result-map lookups only

            snap = snapshots.get(cid_str)
            price = float(snap["price"]) if snap and snap["price"] else None
            price_change = (
                float(snap["price_change_pct"])
                if snap and snap["price_change_pct"]
                else None
            )
            last_updated = snap["created_at"] if snap else None

            sentiment = sentiment_current.get(cid_str)
            prior = sentiment_prior.get(cid_str)
            sentiment_delta: int | None = None
            if sentiment is not None and prior is not None:
                sentiment_delta = sentiment - prior

            filings_count = filings_map.get(cid_str, 0)
            risk_count, risk_sev_rank = risk_map.get(cid_str, (0, None))
            max_severity = sev_map.get(risk_sev_rank) if risk_sev_rank else None
            brief_id_str = brief_map.get(cid_str)
            brief_id = uuid.UUID(brief_id_str) if brief_id_str else None

            change_score = _compute_change_score(
                new_filings=filings_count,
                risk_flags=risk_count,
                price_change_pct=price_change,
                sentiment_delta=sentiment_delta,
            )

            cards.append(
                CompanyCard(
                    company_id=cid,
                    ticker=company.ticker,
                    name=company.name,
                    sector=company.sector,
                    price=price,
                    price_change_pct=price_change,
                    sentiment_score=sentiment,
                    sentiment_delta=sentiment_delta,
                    new_filings_count=filings_count,
                    risk_flag_count=risk_count,
                    risk_flag_max_severity=max_severity,
                    last_updated_at=last_updated,
                    brief_id=brief_id,
                    change_score=change_score,
                )
            )

        cards.sort(key=lambda c: c.change_score, reverse=True)
        return cards

    # ------------------------------------------------------------------
    # Batch helpers (one query per data type for all company IDs)
    # ------------------------------------------------------------------

    async def _batch_latest_snapshots(
        self, cids: list[uuid.UUID]
    ) -> dict[str, dict[str, Any]]:
        """Batch-fetch the latest snapshot per company via window function."""
        sql = text(
            """
            SELECT DISTINCT ON (company_id)
                   company_id, price, price_change_pct, created_at
            FROM financial_snapshots
            WHERE company_id = ANY(:cids)
            ORDER BY company_id, snapshot_date DESC
            """
        )
        result = await self._session.execute(sql, {"cids": cids})
        return {
            str(r.company_id): {
                "price": r.price,
                "price_change_pct": r.price_change_pct,
                "created_at": r.created_at,
            }
            for r in result.mappings()
        }

    async def _batch_avg_sentiment(
        self, cids: list[uuid.UUID], days: int, offset_days: int = 0
    ) -> dict[str, int]:
        """Batch-fetch average sentiment per company for a time window."""
        if offset_days:
            sql = text(
                """
                SELECT company_id, AVG(score)::int AS avg_score
                FROM sentiment_records
                WHERE company_id = ANY(:cids)
                  AND scored_at >= NOW() - MAKE_INTERVAL(days => :days)
                  AND scored_at <  NOW() - MAKE_INTERVAL(days => :offset)
                GROUP BY company_id
                """
            )
            result = await self._session.execute(
                sql, {"cids": cids, "days": days, "offset": offset_days}
            )
        else:
            sql = text(
                """
                SELECT company_id, AVG(score)::int AS avg_score
                FROM sentiment_records
                WHERE company_id = ANY(:cids)
                  AND scored_at >= NOW() - MAKE_INTERVAL(days => :days)
                GROUP BY company_id
                """
            )
            result = await self._session.execute(
                sql, {"cids": cids, "days": days}
            )
        return {str(r.company_id): r.avg_score for r in result.mappings()}

    async def _batch_new_filings(
        self, cids: list[uuid.UUID], days: int
    ) -> dict[str, int]:
        """Batch-count new documents per company within the lookback window."""
        sql = text(
            """
            SELECT company_id, COUNT(*) AS cnt
            FROM documents
            WHERE company_id = ANY(:cids)
              AND ingested_at >= NOW() - MAKE_INTERVAL(days => :days)
            GROUP BY company_id
            """
        )
        result = await self._session.execute(
            sql, {"cids": cids, "days": days}
        )
        return {str(r.company_id): r.cnt for r in result.mappings()}

    async def _batch_risk_summary(
        self, cids: list[uuid.UUID]
    ) -> dict[str, tuple[int, int | None]]:
        """Batch-fetch risk flag count and max severity rank per company.

        Returns **all-time** risk flags — there is no time-window filter here
        because risk flags have no ``resolved_at`` column.  A flag detected six
        months ago is still a live signal until the model grows a resolution
        mechanism.  Callers should interpret the count as "total active flags"
        rather than "flags this period".
        """
        sql = text(
            """
            SELECT company_id,
                   COUNT(*) AS cnt,
                   MAX(CASE severity
                       WHEN 'critical' THEN 4
                       WHEN 'high' THEN 3
                       WHEN 'medium' THEN 2
                       WHEN 'low' THEN 1
                       ELSE 0
                   END) AS max_sev_rank
            FROM risk_flags
            WHERE company_id = ANY(:cids)
            GROUP BY company_id
            """
        )
        result = await self._session.execute(sql, {"cids": cids})
        return {
            str(r.company_id): (r.cnt, r.max_sev_rank)
            for r in result.mappings()
        }

    async def _batch_latest_briefs(
        self, cids: list[uuid.UUID], user_id: uuid.UUID
    ) -> dict[str, str]:
        """Batch-fetch latest brief ID per company for a user."""
        sql = text(
            """
            SELECT DISTINCT ON (company_id)
                   company_id, id AS brief_id
            FROM analyst_briefs
            WHERE company_id = ANY(:cids)
              AND user_id = :uid
            ORDER BY company_id, generated_at DESC
            """
        )
        result = await self._session.execute(
            sql, {"cids": cids, "uid": user_id}
        )
        return {str(r.company_id): str(r.brief_id) for r in result.mappings()}
