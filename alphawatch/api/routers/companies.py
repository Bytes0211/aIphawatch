"""Company resolution and lookup endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.api.dependencies import get_current_user, get_db
from alphawatch.repositories.companies import CompanyRepository
from alphawatch.schemas.auth import CurrentUser
from alphawatch.schemas.company import CompanyResolveResponse, CompanyResponse

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/resolve", response_model=CompanyResolveResponse)
async def resolve_company(
    q: str = Query(..., min_length=1, description="Ticker or company name to search"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyResolveResponse:
    """Resolve a ticker or company name to matching companies.

    Performs a case-insensitive prefix match on ticker and a
    substring match on company name. Returns up to 20 results.

    Args:
        q: Search query string.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        Matching companies and the original query.
    """
    repo = CompanyRepository(db)
    companies = await repo.resolve(q)
    return CompanyResolveResponse(
        results=[CompanyResponse.model_validate(c) for c in companies],
        query=q,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    """Get a company by ID.

    Args:
        company_id: The company UUID.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        The company data.

    Raises:
        HTTPException: 404 if company not found, 422 if malformed UUID.
    """
    repo = CompanyRepository(db)
    company = await repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse.model_validate(company)
