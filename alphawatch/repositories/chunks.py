"""Document chunk repository — pgvector similarity search for RAG retrieval."""

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.agents.state import ChunkResult
from alphawatch.models.document import DocumentChunk


class ChunkRepository:
    """Data access for document chunks with pgvector similarity search.

    Provides ANN (approximate nearest-neighbour) retrieval over the
    HNSW index on ``document_chunks.embedding`` using cosine distance.

    Args:
        session: An async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def similarity_search(
        self,
        company_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 8,
        source_types: list[str] | None = None,
    ) -> list[ChunkResult]:
        """Retrieve the top-k most similar chunks for a query embedding.

        Performs cosine similarity search restricted to a single company
        to enforce tenant-safe scoping. Optionally filters by source type
        (e.g. only edgar_10k and edgar_10q filings).

        Args:
            company_id: Restrict search to chunks belonging to this company.
            query_embedding: 1536-dim query vector from Titan Embeddings v2.
            top_k: Number of nearest neighbours to return.
            source_types: Optional whitelist of source type strings.
                When omitted, all source types are searched.

        Returns:
            List of ChunkResult objects ordered by descending similarity,
            capped at ``top_k`` entries.
        """
        # Build the base query joining chunks → documents for metadata
        # The <=> operator is pgvector cosine distance (lower = more similar).
        # We convert to similarity = 1 - distance so higher = better.
        source_filter = ""
        bind_params: dict[str, Any] = {
            "embedding": str(query_embedding),
            "company_id": str(company_id),
            "top_k": top_k,
        }
        if source_types:
            source_filter = "AND d.source_type = ANY(:source_types)"
            bind_params["source_types"] = source_types

        sql = text(
            f"""
            SELECT
                dc.id              AS chunk_id,
                dc.document_id     AS document_id,
                dc.content         AS content,
                1 - (dc.embedding <=> CAST(:embedding AS vector))
                                   AS similarity,
                d.source_type      AS source_type,
                d.source_url       AS source_url,
                d.title            AS title,
                dc.metadata        AS metadata
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.company_id = :company_id
              AND dc.embedding IS NOT NULL
              {source_filter}
            ORDER BY dc.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
            """
        )

        result = await self._session.execute(sql, bind_params)

        rows = result.mappings().all()
        return [
            ChunkResult(
                chunk_id=str(row["chunk_id"]),
                document_id=str(row["document_id"]),
                content=row["content"],
                similarity=float(row["similarity"]),
                source_type=row["source_type"],
                source_url=row["source_url"] or "",
                title=row["title"],
                metadata=dict(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]

    async def get_chunk_by_id(
        self,
        chunk_id: uuid.UUID,
    ) -> DocumentChunk | None:
        """Fetch a single chunk by primary key.

        Args:
            chunk_id: UUID of the DocumentChunk.

        Returns:
            The DocumentChunk if found, otherwise None.
        """
        return await self._session.get(DocumentChunk, chunk_id)

    async def get_chunks_by_ids(
        self,
        chunk_ids: list[uuid.UUID],
    ) -> list[DocumentChunk]:
        """Fetch multiple chunks by their primary keys.

        Useful for chat chunk cache hydration — loads previously
        retrieved chunks without re-running vector search.

        Args:
            chunk_ids: List of DocumentChunk UUIDs to retrieve.

        Returns:
            List of DocumentChunk objects (order not guaranteed).
        """
        if not chunk_ids:
            return []

        stmt = select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_chunks_for_company(
        self,
        company_id: uuid.UUID,
        source_types: list[str] | None = None,
    ) -> int:
        """Count indexed chunks available for a company.

        Useful for deciding whether there is enough data to generate
        a meaningful brief before invoking BriefGraph.

        Args:
            company_id: The company UUID.
            source_types: Optional filter by source type.

        Returns:
            Total number of chunks with embeddings for this company.
        """
        source_filter = ""
        bind_params: dict[str, Any] = {"company_id": str(company_id)}
        if source_types:
            source_filter = "AND d.source_type = ANY(:source_types)"
            bind_params["source_types"] = source_types

        count_sql = text(
            f"""
            SELECT COUNT(*)
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.company_id = :company_id
              AND dc.embedding IS NOT NULL
              {source_filter}
            """
        )

        result = await self._session.execute(count_sql, bind_params)
        return result.scalar_one() or 0
