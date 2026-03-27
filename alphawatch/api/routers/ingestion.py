"""Ingestion trigger endpoint (admin-only)."""


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.api.dependencies import get_db, require_role
from alphawatch.repositories.companies import CompanyRepository
from alphawatch.schemas.auth import CurrentUser

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


class IngestionTriggerRequest(BaseModel):
    """Request body for triggering ingestion.

    Attributes:
        ticker: Stock ticker symbol to ingest filings for.
        filing_types: Optional list of filing types (default: 10-K, 10-Q, 8-K).
    """

    ticker: str
    filing_types: list[str] | None = None


class IngestionTriggerResponse(BaseModel):
    """Response after triggering ingestion.

    Attributes:
        status: Trigger status.
        company_id: The resolved company UUID.
        ticker: The ticker symbol.
        message: Human-readable status message.
    """

    status: str
    company_id: str
    ticker: str
    message: str


@router.post("/trigger", response_model=IngestionTriggerResponse)
async def trigger_ingestion(
    body: IngestionTriggerRequest,
    user: CurrentUser = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
) -> IngestionTriggerResponse:
    """Manually trigger EDGAR ingestion for a company.

    Admin-only endpoint. Resolves the ticker to a company, then runs
    the IngestionGraph asynchronously.

    Args:
        body: Request body with ticker and optional filing types.
        user: The authenticated admin user (injected).
        db: Database session (injected).

    Returns:
        Trigger status with company details.

    Raises:
        HTTPException: 404 if ticker not found.
    """
    company_repo = CompanyRepository(db)
    company = await company_repo.get_by_ticker(body.ticker)
    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"Company with ticker '{body.ticker.upper()}' not found",
        )

    # Import here to avoid circular imports and heavy graph init at module load
    from alphawatch.agents.graphs.ingestion import build_ingestion_graph

    graph = build_ingestion_graph()

    # Build initial state
    initial_state = {
        "tenant_id": user.tenant_id,
        "user_id": user.user_id,
        "company_id": str(company.id),
        "ticker": company.ticker,
        "filing_types": body.filing_types or ["10-K", "10-Q", "8-K"],
        "errors": [],
        "metadata": {"cik": company.cik} if company.cik else {},
    }

    # Run the graph (synchronous invocation for now;
    # Celery async dispatch comes in Step 14)
    try:
        result = await graph.ainvoke(initial_state)
        stored = result.get("embeddings_stored", 0)
        errors = result.get("errors", [])

        if errors:
            return IngestionTriggerResponse(
                status="completed_with_errors",
                company_id=str(company.id),
                ticker=company.ticker,
                message=f"Stored {stored} chunks with {len(errors)} error(s)",
            )

        return IngestionTriggerResponse(
            status="completed",
            company_id=str(company.id),
            ticker=company.ticker,
            message=f"Ingestion complete: {stored} chunks stored",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {exc}",
        )
