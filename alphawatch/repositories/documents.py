"""Document repository — storage and deduplication."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.agents.state import Chunk, ParsedDoc
from alphawatch.models.document import Document, DocumentChunk


class DocumentRepository:
    """Data access for documents and document chunks.

    Handles deduplication via content_hash and bulk chunk insertion.

    Args:
        session: An async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_hash(
        self, company_id: uuid.UUID, content_hash: str
    ) -> Document | None:
        """Check if a document already exists by content hash.

        Args:
            company_id: The company UUID.
            content_hash: SHA-256 hash of the document text.

        Returns:
            The Document if found (duplicate), otherwise None.
        """
        stmt = select(Document).where(
            Document.company_id == company_id,
            Document.content_hash == content_hash,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_document(
        self, company_id: uuid.UUID, parsed: ParsedDoc
    ) -> Document:
        """Create a new document record.

        Args:
            company_id: The company UUID.
            parsed: Parsed document data.

        Returns:
            The newly created Document.
        """
        doc = Document(
            company_id=company_id,
            source_type=parsed.source_type,
            source_url=parsed.source_url,
            title=parsed.title,
            content_hash=parsed.content_hash,
            raw_text=parsed.raw_text,
            metadata_=parsed.metadata,
        )
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def bulk_insert_chunks(
        self,
        document_id: uuid.UUID,
        company_id: uuid.UUID,
        chunks: list[Chunk],
    ) -> int:
        """Bulk insert document chunks with embeddings.

        Args:
            document_id: The parent document UUID.
            company_id: The company UUID (denormalized for filtering).
            chunks: List of Chunk objects with embeddings populated.

        Returns:
            Number of chunks inserted.
        """
        db_chunks = [
            DocumentChunk(
                document_id=document_id,
                company_id=company_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                embedding=chunk.embedding,
                metadata_=chunk.metadata,
            )
            for chunk in chunks
        ]
        self._session.add_all(db_chunks)
        await self._session.flush()
        return len(db_chunks)
