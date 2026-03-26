"""SentimentGraph node functions.

Each node receives the full SentimentState and returns a partial
state update dict. Errors are accumulated in state['errors'].
"""

import hashlib
import logging
import uuid
from typing import Any

from alphawatch.agents.state import NewsArticleRef, ParsedDoc, SentimentState
from alphawatch.services.bedrock import BedrockClient
from alphawatch.services.news import NewsClient

logger = logging.getLogger(__name__)


async def fetch_news(state: SentimentState) -> dict[str, Any]:
    """Fetch recent news articles for the company.

    Args:
        state: Current sentiment state with ticker and company_name.

    Returns:
        Partial state update with articles list.
    """
    ticker = state["ticker"]
    company_name = state.get("company_name", "")
    days_back = state.get("days_back", 7)
    errors = list(state.get("errors", []))

    client = NewsClient()
    try:
        articles = await client.get_company_news(
            ticker=ticker,
            company_name=company_name if company_name else None,
            days_back=days_back,
        )

        # Convert to NewsArticleRef dataclass
        article_refs = [
            NewsArticleRef(
                title=article.title,
                description=article.description,
                url=article.url,
                source_name=article.source_name,
                published_at=article.published_at,
                content=article.content,
            )
            for article in articles
        ]

        logger.info(
            "fetch_news: %s found %d articles in last %d days",
            ticker,
            len(article_refs),
            days_back,
        )
        return {"articles": article_refs, "errors": errors}

    except Exception as exc:
        errors.append(f"fetch_news failed: {exc}")
        logger.error("fetch_news error for %s: %s", ticker, exc)
        return {"articles": [], "errors": errors}
    finally:
        await client.close()


def parse_articles(state: SentimentState) -> dict[str, Any]:
    """Parse news articles into ParsedDoc format.

    Combines title, description, and content into a single text blob
    for sentiment analysis and storage.

    Args:
        state: Current state with articles to process.

    Returns:
        Partial state update with parsed_documents list.
    """
    articles: list[NewsArticleRef] = state.get("articles", [])
    errors = list(state.get("errors", []))
    parsed: list[ParsedDoc] = []

    for article in articles:
        try:
            # Combine article fields into full text
            parts = []
            if article.title:
                parts.append(f"Title: {article.title}")
            if article.description:
                parts.append(f"Description: {article.description}")
            if article.content:
                parts.append(f"Content: {article.content}")

            raw_text = "\n\n".join(parts)
            content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

            parsed.append(
                ParsedDoc(
                    source_type="news",
                    source_url=article.url,
                    title=article.title,
                    content_hash=content_hash,
                    raw_text=raw_text,
                    metadata={
                        "source_name": article.source_name,
                        "published_at": article.published_at,
                    },
                )
            )

        except Exception as exc:
            errors.append(f"parse_articles failed for {article.title}: {exc}")
            logger.error("parse_articles error: %s", exc)

    logger.info("parse_articles: parsed %d of %d articles", len(parsed), len(articles))
    return {"parsed_documents": parsed, "errors": errors}


async def store_articles(state: SentimentState) -> dict[str, Any]:
    """Store news articles as documents in the database.

    Deduplicates by content_hash to avoid reprocessing the same article.
    News articles are stored with source_type='news' but are NOT chunked
    or embedded (they're only used for sentiment scoring).

    Args:
        state: Current state with parsed_documents.

    Returns:
        Partial state update with stored document IDs in metadata.
    """
    from alphawatch.database import async_session_factory
    from alphawatch.repositories.documents import DocumentRepository

    parsed_docs: list[ParsedDoc] = state.get("parsed_documents", [])
    company_id = uuid.UUID(state["company_id"])
    errors = list(state.get("errors", []))
    stored_docs: list[tuple[str, uuid.UUID]] = []  # (content_hash, doc_id)

    async with async_session_factory() as session:
        repo = DocumentRepository(session)

        for doc in parsed_docs:
            try:
                # Check if already stored
                existing = await repo.find_by_hash(company_id, doc.content_hash)
                if existing:
                    logger.info(
                        "store_articles: skipping duplicate %s", doc.content_hash[:12]
                    )
                    stored_docs.append((doc.content_hash, existing.id))
                    continue

                # Create new document
                db_doc = await repo.create_document(company_id, doc)
                stored_docs.append((doc.content_hash, db_doc.id))
                logger.debug("store_articles: stored %s", doc.title)

            except Exception as exc:
                errors.append(f"store_articles failed for {doc.title}: {exc}")
                logger.error("store_articles error: %s", exc)
                await session.rollback()
                continue

        await session.commit()

    logger.info("store_articles: stored/found %d articles", len(stored_docs))
    # Store doc IDs in metadata for next node
    metadata = dict(state.get("metadata", {}))
    metadata["stored_docs"] = stored_docs
    return {"metadata": metadata, "errors": errors}


async def score_sentiments(state: SentimentState) -> dict[str, Any]:
    """Score sentiment for each stored article using Bedrock Claude.

    Runs the synchronous boto3 calls in a thread executor to avoid
    blocking the async event loop.

    Args:
        state: Current state with stored documents in metadata.

    Returns:
        Partial state update with sentiment_scores list.
    """
    import asyncio

    parsed_docs: list[ParsedDoc] = state.get("parsed_documents", [])
    stored_docs: list[tuple[str, uuid.UUID]] = state.get("metadata", {}).get(
        "stored_docs", []
    )
    ticker = state["ticker"]
    company_name = state.get("company_name", ticker)
    errors = list(state.get("errors", []))

    # Build mapping from content_hash to document_id
    hash_to_doc_id = {content_hash: doc_id for content_hash, doc_id in stored_docs}

    sentiment_scores: list[tuple[str, int]] = []  # (doc_id_str, score)

    if not parsed_docs:
        return {"sentiment_scores": sentiment_scores, "errors": errors}

    try:
        client = BedrockClient()
        loop = asyncio.get_running_loop()

        for doc in parsed_docs:
            doc_id = hash_to_doc_id.get(doc.content_hash)
            if not doc_id:
                logger.warning(
                    "score_sentiments: no doc_id for hash %s", doc.content_hash[:12]
                )
                continue

            try:
                # Run synchronous boto3 call off the event loop
                score = await loop.run_in_executor(
                    None,
                    client.score_sentiment,
                    doc.raw_text,
                    company_name,
                    ticker,
                )
                sentiment_scores.append((str(doc_id), score))
                logger.debug(
                    "score_sentiments: %s scored %d for %s",
                    ticker,
                    score,
                    doc.title[:50],
                )

            except Exception as exc:
                errors.append(f"score_sentiments failed for {doc.title}: {exc}")
                logger.error("score_sentiments error: %s", exc)

        logger.info(
            "score_sentiments: scored %d of %d articles",
            len(sentiment_scores),
            len(parsed_docs),
        )

    except Exception as exc:
        errors.append(f"score_sentiments initialization failed: {exc}")
        logger.error("score_sentiments error: %s", exc)

    return {"sentiment_scores": sentiment_scores, "errors": errors}


async def store_sentiments(state: SentimentState) -> dict[str, Any]:
    """Store sentiment scores in the database.

    Args:
        state: Current state with sentiment_scores.

    Returns:
        Partial state update with scores_stored count.
    """
    from alphawatch.database import async_session_factory
    from alphawatch.repositories.sentiment import SentimentRepository

    sentiment_scores: list[tuple[str, int]] = state.get("sentiment_scores", [])
    company_id = uuid.UUID(state["company_id"])
    errors = list(state.get("errors", []))
    stored_count = 0

    if not sentiment_scores:
        logger.info("store_sentiments: no scores to store")
        return {"scores_stored": 0, "errors": errors}

    async with async_session_factory() as session:
        repo = SentimentRepository(session)

        # Prepare bulk insert data
        records = [
            (
                company_id,
                uuid.UUID(doc_id_str),
                score,
                "news",  # source_type
            )
            for doc_id_str, score in sentiment_scores
        ]

        try:
            stored_count = await repo.bulk_create_sentiments(records)
            await session.commit()
            logger.info("store_sentiments: stored %d sentiment records", stored_count)

        except Exception as exc:
            errors.append(f"store_sentiments failed: {exc}")
            logger.error("store_sentiments error: %s", exc)
            await session.rollback()

    return {"scores_stored": stored_count, "errors": errors}


def handle_errors(state: SentimentState) -> dict[str, Any]:
    """Log accumulated errors from the sentiment pipeline.

    Args:
        state: Current state with errors list.

    Returns:
        Empty state update (terminal node).
    """
    errors = state.get("errors", [])
    ticker = state.get("ticker", "unknown")

    if errors:
        for error in errors:
            logger.error("SentimentGraph error [%s]: %s", ticker, error)
    else:
        scores_stored = state.get("scores_stored", 0)
        logger.info(
            "SentimentGraph completed successfully [%s]: %d sentiments stored",
            ticker,
            scores_stored,
        )

    return {}
