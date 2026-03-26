"""Sentiment record repository — storage and retrieval."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.models.financial import SentimentRecord


class SentimentRepository:
    """Data access for sentiment records.

    Handles sentiment score storage and aggregation queries.

    Args:
        session: An async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_sentiment(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        score: int,
        source_type: str,
    ) -> SentimentRecord:
        """Create a new sentiment record.

        Args:
            company_id: The company UUID.
            document_id: The document UUID that was scored.
            score: Sentiment score from -100 to +100.
            source_type: Type of source scored (news, edgar_10k, etc.).

        Returns:
            The newly created SentimentRecord.

        Raises:
            ValueError: If score is out of range.
        """
        if not -100 <= score <= 100:
            raise ValueError(
                f"Sentiment score must be between -100 and +100, got {score}"
            )

        record = SentimentRecord(
            company_id=company_id,
            document_id=document_id,
            score=score,
            source_type=source_type,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def bulk_create_sentiments(
        self,
        records: list[tuple[uuid.UUID, uuid.UUID, int, str]],
    ) -> int:
        """Bulk create sentiment records.

        Args:
            records: List of (company_id, document_id, score, source_type) tuples.

        Returns:
            Number of records created.
        """
        db_records = [
            SentimentRecord(
                company_id=company_id,
                document_id=document_id,
                score=score,
                source_type=source_type,
            )
            for company_id, document_id, score, source_type in records
        ]
        self._session.add_all(db_records)
        await self._session.flush()
        return len(db_records)

    async def get_recent_sentiments(
        self,
        company_id: uuid.UUID,
        days: int = 7,
        source_type: str | None = None,
    ) -> list[SentimentRecord]:
        """Get recent sentiment records for a company.

        Args:
            company_id: The company UUID.
            days: Number of days to look back.
            source_type: Optional filter by source type.

        Returns:
            List of SentimentRecord objects, newest first.
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        stmt = (
            select(SentimentRecord)
            .where(
                SentimentRecord.company_id == company_id,
                SentimentRecord.scored_at >= cutoff_date,
            )
            .order_by(desc(SentimentRecord.scored_at))
        )

        if source_type:
            stmt = stmt.where(SentimentRecord.source_type == source_type)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_average_sentiment(
        self,
        company_id: uuid.UUID,
        days: int = 7,
        source_type: str | None = None,
    ) -> float | None:
        """Calculate average sentiment score for a company.

        Args:
            company_id: The company UUID.
            days: Number of days to look back.
            source_type: Optional filter by source type.

        Returns:
            Average sentiment score, or None if no records found.
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        stmt = select(func.avg(SentimentRecord.score)).where(
            SentimentRecord.company_id == company_id,
            SentimentRecord.scored_at >= cutoff_date,
        )

        if source_type:
            stmt = stmt.where(SentimentRecord.source_type == source_type)

        result = await self._session.execute(stmt)
        avg_score = result.scalar_one_or_none()
        return float(avg_score) if avg_score is not None else None

    async def get_sentiment_by_source(
        self,
        company_id: uuid.UUID,
        days: int = 7,
    ) -> dict[str, float]:
        """Get average sentiment scores grouped by source type.

        Args:
            company_id: The company UUID.
            days: Number of days to look back.

        Returns:
            Dict mapping source_type to average score.
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        stmt = (
            select(
                SentimentRecord.source_type,
                func.avg(SentimentRecord.score).label("avg_score"),
            )
            .where(
                SentimentRecord.company_id == company_id,
                SentimentRecord.scored_at >= cutoff_date,
            )
            .group_by(SentimentRecord.source_type)
        )

        result = await self._session.execute(stmt)
        return {
            source_type: float(avg_score) for source_type, avg_score in result.all()
        }

    async def get_sentiment_trend(
        self,
        company_id: uuid.UUID,
        days: int = 30,
    ) -> list[tuple[str, float]]:
        """Get daily average sentiment scores for trend analysis.

        Args:
            company_id: The company UUID.
            days: Number of days to look back.

        Returns:
            List of (date_string, avg_score) tuples, oldest first.
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        # Cast scored_at to date and group by it
        date_col = func.date(SentimentRecord.scored_at)

        stmt = (
            select(
                date_col.label("scored_date"),
                func.avg(SentimentRecord.score).label("avg_score"),
            )
            .where(
                SentimentRecord.company_id == company_id,
                SentimentRecord.scored_at >= cutoff_date,
            )
            .group_by(date_col)
            .order_by(date_col)
        )

        result = await self._session.execute(stmt)
        return [(str(date), float(avg_score)) for date, avg_score in result.all()]
