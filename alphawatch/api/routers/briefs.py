"""Analyst brief API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.api.dependencies import get_current_user, get_db
from alphawatch.repositories.briefs import BriefRepository
from alphawatch.repositories.companies import CompanyRepository
from alphawatch.schemas.auth import CurrentUser
from alphawatch.schemas.brief import (
    BriefGenerateRequest,
    BriefGenerateResponse,
    BriefResponse,
    BriefSectionResponse,
    BriefSummaryResponse,
)

router = APIRouter(prefix="/api/companies", tags=["briefs"])


@router.get("/{company_id}/brief", response_model=BriefResponse | None)
async def get_latest_brief(
    company_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BriefResponse | None:
    """Get the latest analyst brief for a company.

    Returns the most recent brief with all sections, or null if
    no brief has been generated yet.

    Args:
        company_id: The company UUID.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        The latest brief with sections, or None.

    Raises:
        HTTPException: 404 if company not found.
    """
    company_repo = CompanyRepository(db)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    brief_repo = BriefRepository(db)
    brief = await brief_repo.get_latest_for_user_company(
        user_id=uuid.UUID(user.user_id),
        company_id=company_id,
    )

    if not brief:
        return None

    return BriefResponse(
        id=brief.id,
        company_id=brief.company_id,
        user_id=brief.user_id,
        session_id=brief.session_id,
        generated_at=brief.generated_at,
        sections=[
            BriefSectionResponse(
                id=s.id,
                section_type=s.section_type,
                section_order=s.section_order,
                content=s.content,
                created_at=s.created_at,
            )
            for s in sorted(brief.sections, key=lambda s: s.section_order)
        ],
    )


@router.post(
    "/{company_id}/brief/generate",
    response_model=BriefGenerateResponse,
)
async def generate_brief(
    company_id: uuid.UUID,
    body: BriefGenerateRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BriefGenerateResponse:
    """Force-generate a new analyst brief for a company.

    Runs the BriefGraph to produce all 8 sections. The previous brief
    (if any) is not deleted — both are retained for comparison.

    Args:
        company_id: The company UUID.
        body: Optional request body with custom query text.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        Generation status with brief ID.

    Raises:
        HTTPException: 404 if company not found, 500 on generation failure.
    """
    company_repo = CompanyRepository(db)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Import here to avoid heavy graph init at module load
    from alphawatch.agents.graphs.brief import build_brief_graph

    graph = build_brief_graph()

    initial_state = {
        "tenant_id": user.tenant_id,
        "user_id": user.user_id,
        "company_id": str(company.id),
        "ticker": company.ticker,
        "company_name": company.name,
        "errors": [],
        "metadata": {},
    }

    if body and body.query_text:
        initial_state["query_text"] = body.query_text

    try:
        result = await graph.ainvoke(initial_state)
        brief_id = result.get("brief_id", "")
        errors = result.get("errors", [])

        if errors:
            return BriefGenerateResponse(
                status="completed_with_errors",
                brief_id=brief_id,
                company_id=str(company.id),
                ticker=company.ticker,
                message=f"Brief generated with {len(errors)} error(s)",
            )

        return BriefGenerateResponse(
            status="completed",
            brief_id=brief_id,
            company_id=str(company.id),
            ticker=company.ticker,
            message="Brief generated successfully",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Brief generation failed: {exc}",
        )


@router.get(
    "/{company_id}/brief/{brief_id}/sections",
    response_model=list[BriefSectionResponse],
)
async def get_brief_sections(
    company_id: uuid.UUID,
    brief_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BriefSectionResponse]:
    """Get all sections for a specific brief.

    Args:
        company_id: The company UUID (for path consistency).
        brief_id: The brief UUID.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        Ordered list of brief sections.

    Raises:
        HTTPException: 404 if brief not found.
    """
    brief_repo = BriefRepository(db)
    brief = await brief_repo.get_brief_by_id(brief_id)

    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")

    return [
        BriefSectionResponse(
            id=s.id,
            section_type=s.section_type,
            section_order=s.section_order,
            content=s.content,
            created_at=s.created_at,
        )
        for s in sorted(brief.sections, key=lambda s: s.section_order)
    ]


@router.get(
    "/{company_id}/briefs",
    response_model=list[BriefSummaryResponse],
)
async def list_briefs(
    company_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BriefSummaryResponse]:
    """List recent briefs for a company (metadata only, no sections).

    Args:
        company_id: The company UUID.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        List of brief summaries ordered by generation date.
    """
    brief_repo = BriefRepository(db)
    briefs = await brief_repo.list_for_user_company(
        user_id=uuid.UUID(user.user_id),
        company_id=company_id,
    )
    return [
        BriefSummaryResponse(
            id=b.id,
            company_id=b.company_id,
            generated_at=b.generated_at,
        )
        for b in briefs
    ]
