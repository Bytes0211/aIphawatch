"""LangGraph state schemas and data classes for agent workflows."""

from dataclasses import dataclass, field
from typing import Any, TypedDict


class BaseState(TypedDict, total=False):
    """Shared state across all LangGraph workflows.

    Attributes:
        tenant_id: Tenant UUID string.
        user_id: User UUID string.
        company_id: Company UUID string.
        ticker: Stock ticker symbol.
        errors: Accumulated non-fatal error messages.
        metadata: Graph-specific passthrough data.
    """

    tenant_id: str
    user_id: str
    company_id: str
    ticker: str
    errors: list[str]
    metadata: dict[str, Any]


@dataclass
class FilingRef:
    """Reference to a discovered SEC filing.

    Attributes:
        accession_number: EDGAR accession number.
        filing_type: Filing type (e.g. 10-K, 10-Q, 8-K).
        filing_date: Date string (YYYY-MM-DD).
        title: Filing title/description.
        url: URL to the filing document.
    """

    accession_number: str
    filing_type: str
    filing_date: str
    title: str
    url: str


@dataclass
class ParsedDoc:
    """A parsed document ready for chunking.

    Attributes:
        source_type: Filing type mapped to DB enum (edgar_10k, etc.).
        source_url: Original filing URL.
        title: Document title.
        content_hash: SHA-256 hash of raw_text for deduplication.
        raw_text: Full extracted text content.
        metadata: Additional metadata (section info, etc.).
    """

    source_type: str
    source_url: str
    title: str
    content_hash: str
    raw_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """A text chunk with optional embedding.

    Attributes:
        content: Chunk text content.
        chunk_index: Sequential index within the parent document.
        embedding: 1536-dim vector, populated after embedding step.
        metadata: Chunk metadata (section, position, etc.).
    """

    content: str
    chunk_index: int
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class IngestionState(BaseState, total=False):
    """State for the IngestionGraph workflow.

    Attributes:
        filing_types: List of filing types to search for.
        new_filings: Discovered filing references from EDGAR.
        parsed_documents: Parsed and deduplicated documents.
        chunks: Text chunks ready for embedding.
        embeddings_stored: Count of chunks stored in the database.
    """

    filing_types: list[str]
    new_filings: list[FilingRef]
    parsed_documents: list[ParsedDoc]
    chunks: list[Chunk]
    embeddings_stored: int
