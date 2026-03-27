"""LangGraph state schemas and data classes for agent workflows."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Required, TypedDict


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
    company_id: Required[str]
    ticker: Required[str]
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


@dataclass
class NewsArticleRef:
    """Reference to a discovered news article.

    Attributes:
        title: Article headline.
        description: Article excerpt/summary.
        url: URL to the full article.
        source_name: Name of the news source.
        published_at: ISO 8601 publication timestamp.
        content: Article content (truncated or full).
    """

    title: str
    description: str
    url: str
    source_name: str
    published_at: str
    content: str = ""


class SentimentState(BaseState, total=False):
    """State for the SentimentGraph workflow.

    Attributes:
        company_name: Full company name for context.
        days_back: Number of days to look back for news.
        articles: Discovered news articles.
        parsed_documents: News articles parsed into documents.
        sentiment_scores: List of (document_id, score) tuples.
        scores_stored: Count of sentiment records stored.
    """

    company_name: str
    days_back: int
    articles: list[NewsArticleRef]
    parsed_documents: list[ParsedDoc]
    sentiment_scores: list[tuple[str, int]]
    scores_stored: int


@dataclass
class ChunkResult:
    """A retrieved document chunk with similarity score.

    Attributes:
        chunk_id: UUID string of the DocumentChunk.
        document_id: UUID string of the parent Document.
        content: Chunk text content.
        similarity: Cosine similarity score (0.0–1.0).
        source_type: Filing type (edgar_10k, edgar_10q, etc.).
        source_url: Original filing URL.
        title: Parent document title.
        metadata: Additional chunk metadata.
    """

    chunk_id: str
    document_id: str
    content: str
    similarity: float
    source_type: str
    source_url: str
    title: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskFlagItem:
    """A single identified risk flag for inclusion in a brief.

    Attributes:
        severity: One of 'high', 'medium', 'low'.
        category: Risk category (e.g. 'regulatory', 'financial', 'operational').
        description: Concise description of the risk.
        source_chunk_ids: Chunk IDs that support this flag.
    """

    severity: str
    category: str
    description: str
    source_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class BriefSectionData:
    """Structured output from a single brief section node.

    Attributes:
        section_type: One of snapshot, what_changed, risk_flags, sentiment,
            sources, executive_summary, suggested_followups.
        section_order: Display ordering integer (1-based).
        content: JSONB-serialisable section payload.
    """

    section_type: str
    section_order: int
    content: dict[str, Any]


class BriefState(BaseState, total=False):
    """State for the BriefGraph workflow.

    Attributes:
        user_id: User UUID string (required — briefs are user-scoped).
        company_name: Full company name for LLM context.
        force_regenerate: When True, bypass existing brief cache.
        query_text: Optional explicit query to seed chunk retrieval.
        retrieved_chunks: Top-k chunks from pgvector similarity search.
        snapshot_section: Built financial snapshot section data.
        what_changed_section: Built what-changed section data.
        risk_flags_section: Built risk flags section data.
        sentiment_section: Built sentiment section data.
        sources_section: Built sources section data.
        executive_summary_section: Built executive summary section data.
        suggested_followups_section: Built suggested follow-ups section data.
        sections: All assembled BriefSectionData objects (populated by fan-in).
        brief_id: UUID string of the persisted AnalystBrief record.
    """

    company_name: str
    force_regenerate: bool
    query_text: str
    retrieved_chunks: list[ChunkResult]
    snapshot_section: BriefSectionData
    what_changed_section: BriefSectionData
    risk_flags_section: BriefSectionData
    sentiment_section: BriefSectionData
    sources_section: BriefSectionData
    executive_summary_section: BriefSectionData
    suggested_followups_section: BriefSectionData
    sections: list[BriefSectionData]
    brief_id: str
