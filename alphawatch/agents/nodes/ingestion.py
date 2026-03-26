"""IngestionGraph node functions.

Each node receives the full IngestionState and returns a partial
state update dict. Errors are accumulated in state['errors'].
"""

import hashlib
import logging
import uuid
from typing import Any

from alphawatch.agents.state import Chunk, FilingRef, IngestionState, ParsedDoc
from alphawatch.services.chunker import chunk_text
from alphawatch.services.edgar import EdgarClient

logger = logging.getLogger(__name__)


async def fetch_filings(state: IngestionState) -> dict[str, Any]:
    """Query EDGAR for new filings for the company.

    Uses CIK from metadata if available for precise filer filtering.

    Args:
        state: Current ingestion state with ticker and filing_types.

    Returns:
        Partial state update with new_filings list.
    """
    ticker = state["ticker"]
    filing_types = state.get("filing_types", ["10-K", "10-Q", "8-K"])
    cik = state.get("metadata", {}).get("cik")
    errors = list(state.get("errors", []))

    client = EdgarClient()
    try:
        filings = await client.search_filings(
            ticker=ticker,
            filing_types=filing_types,
            cik=cik,
        )
        logger.info("fetch_filings: %s found %d filings", ticker, len(filings))
        return {"new_filings": filings, "errors": errors}
    except Exception as exc:
        errors.append(f"fetch_filings failed: {exc}")
        logger.error("fetch_filings error for %s: %s", ticker, exc)
        return {"new_filings": [], "errors": errors}
    finally:
        await client.close()


async def parse_documents(state: IngestionState) -> dict[str, Any]:
    """Download and parse filings, deduplicate by content hash.

    Args:
        state: Current state with new_filings to process.

    Returns:
        Partial state update with parsed_documents list.
    """
    filings: list[FilingRef] = state.get("new_filings", [])
    errors = list(state.get("errors", []))
    parsed: list[ParsedDoc] = []

    client = EdgarClient()
    try:
        for filing in filings:
            try:
                raw_text = await client.download_filing_text(filing.url)
                content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                source_type = EdgarClient.map_filing_type(filing.filing_type)

                parsed.append(
                    ParsedDoc(
                        source_type=source_type,
                        source_url=filing.url,
                        title=filing.title,
                        content_hash=content_hash,
                        raw_text=raw_text,
                        metadata={
                            "filing_type": filing.filing_type,
                            "filing_date": filing.filing_date,
                            "accession_number": filing.accession_number,
                        },
                    )
                )
            except Exception as exc:
                errors.append(
                    f"parse_documents failed for {filing.accession_number}: {exc}"
                )
                logger.error("parse_documents error: %s", exc)
    finally:
        await client.close()

    logger.info("parse_documents: parsed %d of %d filings", len(parsed), len(filings))
    return {"parsed_documents": parsed, "errors": errors}


def chunk_documents(state: IngestionState) -> dict[str, Any]:
    """Split parsed documents into token-sized chunks.

    Tags each chunk's metadata with ``content_hash`` so store_chunks
    can associate chunks with their parent document without re-chunking.

    Args:
        state: Current state with parsed_documents.

    Returns:
        Partial state update with chunks list.
    """
    parsed_docs: list[ParsedDoc] = state.get("parsed_documents", [])
    all_chunks: list[Chunk] = []

    for doc in parsed_docs:
        doc_chunks = chunk_text(
            text=doc.raw_text,
            metadata={
                "source_type": doc.source_type,
                "title": doc.title,
                "content_hash": doc.content_hash,
            },
        )
        all_chunks.extend(doc_chunks)

    logger.info(
        "chunk_documents: %d docs -> %d chunks",
        len(parsed_docs), len(all_chunks),
    )
    return {"chunks": all_chunks}


async def embed_chunks(state: IngestionState) -> dict[str, Any]:
    """Generate embeddings for all chunks via Bedrock Titan.

    Runs the synchronous boto3 calls in a thread executor to avoid
    blocking the async event loop.

    Args:
        state: Current state with chunks to embed.

    Returns:
        Partial state update with chunks that have embeddings populated.
    """
    import asyncio

    chunks: list[Chunk] = state.get("chunks", [])
    errors = list(state.get("errors", []))

    if not chunks:
        return {"chunks": [], "errors": errors}

    try:
        from alphawatch.services.embeddings import EmbeddingsService

        svc = EmbeddingsService()
        texts = [c.content for c in chunks]

        # Run synchronous boto3 calls off the event loop
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(None, svc.embed_batch, texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        logger.info("embed_chunks: embedded %d chunks", len(chunks))
    except Exception as exc:
        errors.append(f"embed_chunks failed: {exc}")
        logger.error("embed_chunks error: %s", exc)

    return {"chunks": chunks, "errors": errors}


async def store_chunks(state: IngestionState) -> dict[str, Any]:
    """Store documents and chunks in the database.

    Deduplicates documents by content_hash before inserting.
    Chunks are keyed to their parent document via ``content_hash``
    in chunk metadata (set by chunk_documents).

    Args:
        state: Current state with parsed_documents and chunks.

    Returns:
        Partial state update with embeddings_stored count.
    """
    from alphawatch.database import async_session_factory
    from alphawatch.repositories.documents import DocumentRepository

    parsed_docs: list[ParsedDoc] = state.get("parsed_documents", [])
    chunks: list[Chunk] = state.get("chunks", [])
    company_id = uuid.UUID(state["company_id"])
    errors = list(state.get("errors", []))
    total_stored = 0

    # Group chunks by content_hash from their metadata
    chunks_by_hash: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        doc_hash = chunk.metadata.get("content_hash", "")
        chunks_by_hash.setdefault(doc_hash, []).append(chunk)

    async with async_session_factory() as session:
        repo = DocumentRepository(session)

        for doc in parsed_docs:
            try:
                existing = await repo.find_by_hash(company_id, doc.content_hash)
                if existing:
                    logger.info(
                        "store_chunks: skipping duplicate %s", doc.content_hash[:12]
                    )
                    continue

                db_doc = await repo.create_document(company_id, doc)
                doc_chunks = chunks_by_hash.get(doc.content_hash, [])
                stored = await repo.bulk_insert_chunks(
                    db_doc.id, company_id, doc_chunks
                )
                total_stored += stored
            except Exception as exc:
                errors.append(f"store_chunks failed for {doc.title}: {exc}")
                logger.error("store_chunks error: %s", exc)
                await session.rollback()
                continue

        await session.commit()

    logger.info("store_chunks: stored %d chunks total", total_stored)
    return {"embeddings_stored": total_stored, "errors": errors}


def handle_errors(state: IngestionState) -> dict[str, Any]:
    """Log accumulated errors from the ingestion pipeline.

    Args:
        state: Current state with errors list.

    Returns:
        Empty state update (terminal node).
    """
    errors = state.get("errors", [])
    if errors:
        for error in errors:
            logger.error("IngestionGraph error: %s", error)
    else:
        logger.info("IngestionGraph completed with no errors")
    return {}
