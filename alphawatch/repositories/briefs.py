"""Analyst brief repository — storage and retrieval of briefs and sections."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from alphawatch.agents.state import BriefSectionData
from alphawatch.models.brief import AnalystBrief, BriefSection


class BriefRepository:
    """Data access for analyst briefs and their sections.

    Briefs are user-scoped; sections are stored separately to enable
    per-section queries, cross-session diffs, and selective export.

    Args:
        session: An async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_brief(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> AnalystBrief:
        """Create a new analyst brief record.

        Args:
            user_id: UUID of the requesting user.
            company_id: UUID of the company being briefed.
            session_id: UUID linking this brief to a generation session.

        Returns:
            The newly created AnalystBrief (not yet committed).
        """
        brief = AnalystBrief(
            user_id=user_id,
            company_id=company_id,
            session_id=session_id,
        )
        self._session.add(brief)
        await self._session.flush()
        return brief

    async def create_section(
        self,
        brief_id: uuid.UUID,
        section_type: str,
        section_order: int,
        content: dict[str, Any],
    ) -> BriefSection:
        """Create a single brief section record.

        Args:
            brief_id: UUID of the parent AnalystBrief.
            section_type: Section identifier string (e.g. 'snapshot').
            section_order: Integer display ordering (1-based).
            content: JSONB-serialisable section payload.

        Returns:
            The newly created BriefSection (not yet committed).
        """
        section = BriefSection(
            brief_id=brief_id,
            section_type=section_type,
            section_order=section_order,
            content=content,
        )
        self._session.add(section)
        await self._session.flush()
        return section

    async def bulk_create_sections(
        self,
        brief_id: uuid.UUID,
        sections: list[BriefSectionData],
    ) -> list[BriefSection]:
        """Bulk create all sections for a brief.

        Args:
            brief_id: UUID of the parent AnalystBrief.
            sections: List of BriefSectionData objects to persist.

        Returns:
            List of created BriefSection ORM objects.
        """
        db_sections = [
            BriefSection(
                brief_id=brief_id,
                section_type=s.section_type,
                section_order=s.section_order,
                content=s.content,
            )
            for s in sections
        ]
        self._session.add_all(db_sections)
        await self._session.flush()
        return db_sections

    async def get_latest_for_user_company(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> AnalystBrief | None:
        """Get the most recently generated brief for a user+company pair.

        Args:
            user_id: UUID of the requesting user.
            company_id: UUID of the company.

        Returns:
            The most recent AnalystBrief with sections eager-loaded,
            or None if no brief exists.
        """
        stmt = (
            select(AnalystBrief)
            .where(
                AnalystBrief.user_id == user_id,
                AnalystBrief.company_id == company_id,
            )
            .options(selectinload(AnalystBrief.sections))
            .order_by(AnalystBrief.generated_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_brief_by_id(
        self,
        brief_id: uuid.UUID,
    ) -> AnalystBrief | None:
        """Get a specific brief by its primary key, with sections.

        Args:
            brief_id: UUID of the AnalystBrief.

        Returns:
            The AnalystBrief with sections eager-loaded, or None.
        """
        stmt = (
            select(AnalystBrief)
            .where(AnalystBrief.id == brief_id)
            .options(selectinload(AnalystBrief.sections))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user_company(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        limit: int = 10,
    ) -> list[AnalystBrief]:
        """List recent briefs for a user+company pair (without sections).

        Args:
            user_id: UUID of the requesting user.
            company_id: UUID of the company.
            limit: Maximum number of briefs to return.

        Returns:
            List of AnalystBrief objects ordered by generated_at desc.
        """
        stmt = (
            select(AnalystBrief)
            .where(
                AnalystBrief.user_id == user_id,
                AnalystBrief.company_id == company_id,
            )
            .order_by(AnalystBrief.generated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_section(
        self,
        brief_id: uuid.UUID,
        section_type: str,
    ) -> BriefSection | None:
        """Get a specific section from a brief by type.

        Args:
            brief_id: UUID of the parent AnalystBrief.
            section_type: The section type identifier to retrieve.

        Returns:
            The BriefSection if found, otherwise None.
        """
        stmt = select(BriefSection).where(
            BriefSection.brief_id == brief_id,
            BriefSection.section_type == section_type,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
