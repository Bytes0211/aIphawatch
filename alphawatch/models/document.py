"""Document and DocumentChunk ORM models."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alphawatch.database import Base


class Document(Base):
    """Ingested document (SEC filing, news article, or upload).

    Attributes:
        id: Primary key UUID.
        company_id: FK to companies.
        source_type: One of edgar_10k, edgar_10q, edgar_8k, news, upload.
        source_url: Original source URL.
        title: Document title.
        content_hash: SHA-256 hash for deduplication.
        raw_text: Full extracted text content.
        metadata: JSONB additional document metadata.
        ingested_at: Ingestion timestamp.
        created_at: Record creation timestamp.
    """

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("company_id", "content_hash", name="uq_documents_company_hash"),
        Index("idx_documents_company", "company_id"),
        Index("idx_documents_source_type", "company_id", "source_type"),
        Index("idx_documents_ingested", "ingested_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    ingested_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document")


class DocumentChunk(Base):
    """Chunked document fragment with vector embedding.

    Attributes:
        id: Primary key UUID.
        document_id: FK to documents.
        company_id: FK to companies (denormalized for efficient filtering).
        chunk_index: Sequential index within the parent document.
        content: Chunk text content.
        embedding: 1536-dim vector from Amazon Titan Embeddings v2.
        metadata: JSONB chunk metadata (section, position, etc.).
        created_at: Record creation timestamp.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_chunks_document_index"
        ),
        Index("idx_chunks_company", "company_id"),
        Index("idx_chunks_document", "document_id"),
        # HNSW index added via raw SQL in migration (not expressible here)
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    document: Mapped["Document"] = relationship(back_populates="chunks")
