"""ChatGraph node functions — top-level imports kept at module level for testability.

Each node receives the full ChatState and returns a partial state update dict.
Errors are accumulated in state['errors'] and never abort the pipeline — the
graph always produces a response, even if it is degraded.

Node execution order
--------------------
prepare_context
    └─ detect_intent
        ├─ (rag / comparison) check_chunk_cache
        │       ├─ (cache miss)  retrieve_chunks
        │       │       ├─ (comparison) competitor_lookup → generate_response
        │       │       └─ (no comparison)              → generate_response
        │       └─ (cache hit)                          → generate_response
        └─ (general)                                    → generate_response
    └─ generate_response
        └─ generate_followups
            └─ persist_turn
                └─ maybe_summarize → handle_errors → END
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from alphawatch.agents.state import (
    ChatMessage,
    ChatState,
    ChunkResult,
    Citation,
)
from alphawatch.config import get_settings
from alphawatch.database import async_session_factory
from alphawatch.repositories.chat import ChatRepository
from alphawatch.repositories.chunks import ChunkRepository
from alphawatch.services.bedrock import BedrockClient
from alphawatch.services.embeddings import EmbeddingsService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUMMARY_THRESHOLD = 20  # trigger rolling summary when session has this many messages
RAW_MESSAGE_WINDOW = 10  # how many recent messages pass verbatim to the LLM
MAX_RETRIEVED_CHUNKS = 8  # top-k for semantic search
CHUNK_CONTEXT_CHARS = 10_000  # max chars of chunk text sent to the LLM
EDGAR_SOURCE_TYPES = ["edgar_10k", "edgar_10q", "edgar_8k"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Returns:
        UTC timestamp string (e.g. '2026-03-26T12:00:00+00:00').
    """
    return datetime.now(timezone.utc).isoformat()


def _format_messages_for_prompt(messages: list[ChatMessage]) -> str:
    """Render a list of ChatMessage objects as a formatted conversation string.

    Args:
        messages: Ordered list of messages to format.

    Returns:
        Multi-line string with role-prefixed lines.
    """
    lines: list[str] = []
    for msg in messages:
        prefix = msg.role.upper()
        lines.append(f"{prefix}: {msg.content}")
    return "\n".join(lines)


def _format_chunks_for_prompt(
    chunks: list[ChunkResult], max_chars: int = CHUNK_CONTEXT_CHARS
) -> str:
    """Format retrieved chunks into a prompt-safe reference block.

    Chunks are included in descending similarity order until the cumulative
    character count reaches ``max_chars``.

    Args:
        chunks: Ordered list of ChunkResult objects.
        max_chars: Maximum total characters to include.

    Returns:
        Formatted string with numbered chunk index, title, and content.
    """
    parts: list[str] = []
    total = 0
    for i, chunk in enumerate(chunks, start=1):
        block = f"[{i}] {chunk.title} ({chunk.source_type})\n{chunk.content}"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n\n---\n\n".join(parts)


def _build_citations(chunks: list[ChunkResult]) -> list[Citation]:
    """Build a citation list from retrieved chunks, deduplicated by document.

    Args:
        chunks: Chunks used as sources for the current response.

    Returns:
        List of Citation objects, one per unique document.
    """
    seen: set[str] = set()
    citations: list[Citation] = []
    for chunk in chunks:
        if chunk.document_id not in seen:
            seen.add(chunk.document_id)
            citations.append(
                Citation(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    source_type=chunk.source_type,
                    source_url=chunk.source_url,
                    excerpt=chunk.content[:200],
                )
            )
    return citations


# ---------------------------------------------------------------------------
# Node 1 — prepare_context
# ---------------------------------------------------------------------------


async def prepare_context(state: ChatState) -> dict[str, Any]:
    """Load the session from the database and build the LLM context window.

    Constructs ``llm_context`` from:
    - ``context_summary`` (rolling summary of messages prior to the window)
    - the last ``RAW_MESSAGE_WINDOW`` raw messages from the session

    Also hydrates ``messages``, ``retrieved_chunk_ids``,
    ``context_summary``, and ``summary_through`` from the database so
    downstream nodes have the full session state without additional queries.

    Args:
        state: Current chat state with session_id, company_id, and ticker.

    Returns:
        Partial state update with messages, context_summary, summary_through,
        retrieved_chunk_ids, and llm_context populated.
    """
    session_id_str = state.get("session_id", "")
    errors = list(state.get("errors", []))

    if not session_id_str:
        errors.append("prepare_context: session_id is required")
        return {
            "messages": [],
            "context_summary": "",
            "summary_through": 0,
            "retrieved_chunk_ids": [],
            "llm_context": [],
            "errors": errors,
        }

    try:
        session_id = uuid.UUID(session_id_str)

        async with async_session_factory() as db:
            repo = ChatRepository(db)
            db_session = await repo.get_session(session_id)

        if db_session is None:
            errors.append(f"prepare_context: session {session_id_str} not found")
            return {
                "messages": [],
                "context_summary": "",
                "summary_through": 0,
                "retrieved_chunk_ids": [],
                "llm_context": [],
                "errors": errors,
            }

        # Deserialise stored JSONB messages → ChatMessage dataclasses
        raw_messages: list[dict[str, Any]] = list(db_session.messages or [])
        messages: list[ChatMessage] = [
            ChatMessage(
                role=m.get("role", "user"),
                content=m.get("content", ""),
                citations=[Citation(**c) for c in m.get("citations", [])],
                turn_index=m.get("turn_index", i),
                created_at=m.get("created_at", ""),
            )
            for i, m in enumerate(raw_messages)
        ]

        context_summary: str = db_session.context_summary or ""
        summary_through: int = db_session.context_summary_through or 0
        retrieved_chunk_ids: list[str] = [
            str(cid) for cid in (db_session.retrieved_chunk_ids or [])
        ]

        # Build the trimmed context window for the LLM
        llm_context: list[ChatMessage] = []

        # Always prepend the rolling summary as a synthetic system message
        if context_summary:
            llm_context.append(
                ChatMessage(
                    role="system",
                    content=f"[Earlier conversation summary]\n{context_summary}",
                )
            )

        # Append the most recent RAW_MESSAGE_WINDOW messages verbatim
        llm_context.extend(messages[-RAW_MESSAGE_WINDOW:])

        logger.info(
            "prepare_context: session=%s messages=%d cached_chunks=%d",
            session_id_str,
            len(messages),
            len(retrieved_chunk_ids),
        )

        return {
            "messages": messages,
            "context_summary": context_summary,
            "summary_through": summary_through,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "llm_context": llm_context,
            "errors": errors,
        }

    except Exception as exc:
        errors.append(f"prepare_context failed: {exc}")
        logger.error("prepare_context error: %s", exc)
        return {
            "messages": [],
            "context_summary": "",
            "summary_through": 0,
            "retrieved_chunk_ids": [],
            "llm_context": [],
            "errors": errors,
        }


# ---------------------------------------------------------------------------
# Node 2 — detect_intent
# ---------------------------------------------------------------------------


async def detect_intent(state: ChatState) -> dict[str, Any]:
    """Classify the user message and extract any comparison entity.

    Uses Claude Haiku to classify intent into one of three categories:
    - ``rag``: single-company question requiring document retrieval
    - ``comparison``: question comparing this company to another ticker
    - ``general``: conversational or clarification question (no retrieval)

    For ``comparison`` intent, also extracts the second ticker symbol.

    Falls back to ``rag`` on any error so the graph always retrieves
    context rather than answering blindly.

    Args:
        state: Current chat state with user_message, ticker, and company_name.

    Returns:
        Partial state update with intent and (optionally) comparison_entity.
    """
    user_message = state.get("user_message", "")
    ticker = state["ticker"]
    company_name = state.get("company_name", ticker)
    errors = list(state.get("errors", []))
    settings = get_settings()

    if not user_message:
        return {"intent": "general", "comparison_entity": "", "errors": errors}

    prompt = f"""You are classifying a user's question about {company_name} ({ticker}).

User question: "{user_message}"

Classify the intent as ONE of:
- "rag": requires looking up facts from SEC filings or financial data about {ticker}
- "comparison": asks how {ticker} compares to another company (extract the other ticker)
- "general": conversational, clarification, or follow-up requiring no document lookup

Return JSON only:
{{"intent": "rag"|"comparison"|"general", "comparison_ticker": "<TICKER or empty string>"}}"""

    try:
        client = BedrockClient(model_id=settings.bedrock_followup_model_id)
        loop = asyncio.get_running_loop()
        result: dict[str, Any] = await loop.run_in_executor(
            None,
            lambda: client.invoke_with_json(
                prompt=prompt,
                model_id=settings.bedrock_followup_model_id,
                max_tokens=100,
                temperature=0.0,
            ),
        )
        intent = result.get("intent", "rag")
        if intent not in {"rag", "comparison", "general"}:
            intent = "rag"
        comparison_entity = result.get("comparison_ticker", "").strip().upper()

        logger.info(
            "detect_intent: '%s' → intent=%s comparison=%s",
            user_message[:60],
            intent,
            comparison_entity or "(none)",
        )
        return {
            "intent": intent,
            "comparison_entity": comparison_entity,
            "errors": errors,
        }

    except Exception as exc:
        errors.append(f"detect_intent failed: {exc}")
        logger.error("detect_intent error: %s", exc)
        # Safe fallback: treat as RAG so we always retrieve context
        return {"intent": "rag", "comparison_entity": "", "errors": errors}


# ---------------------------------------------------------------------------
# Node 3 — check_chunk_cache
# ---------------------------------------------------------------------------


async def check_chunk_cache(state: ChatState) -> dict[str, Any]:
    """Attempt to serve this turn entirely from the session chunk cache.

    Loads all previously retrieved chunks from the database by their cached
    IDs. If the cache is non-empty (i.e. ≥1 chunk loaded), it sets
    ``cache_hit=True`` so the graph can skip a new embedding + similarity
    search.  A full retrieval pass still runs if the cache is empty.

    Args:
        state: Current chat state with retrieved_chunk_ids and company_id.

    Returns:
        Partial state update with retrieved_chunks and cache_hit flag.
    """
    cached_ids = state.get("retrieved_chunk_ids", [])
    errors = list(state.get("errors", []))

    if not cached_ids:
        return {"retrieved_chunks": [], "cache_hit": False, "errors": errors}

    try:
        chunk_uuids = [uuid.UUID(cid) for cid in cached_ids]

        async with async_session_factory() as db:
            repo = ChunkRepository(db)
            db_chunks = await repo.get_chunks_by_ids(chunk_uuids)

        if not db_chunks:
            return {"retrieved_chunks": [], "cache_hit": False, "errors": errors}

        # Reconstruct ChunkResult objects from ORM models
        chunks: list[ChunkResult] = []
        for c in db_chunks:
            # Fetch parent document metadata (already eager-loadable via join)
            chunks.append(
                ChunkResult(
                    chunk_id=str(c.id),
                    document_id=str(c.document_id),
                    content=c.content,
                    similarity=1.0,  # cached — treat as top-similarity
                    source_type=c.metadata_.get("source_type", "unknown"),
                    source_url=c.metadata_.get("source_url", ""),
                    title=c.metadata_.get("title", ""),
                    metadata=dict(c.metadata_ or {}),
                )
            )

        logger.info(
            "check_chunk_cache: loaded %d cached chunks (hit=%s)",
            len(chunks),
            len(chunks) > 0,
        )
        return {
            "retrieved_chunks": chunks,
            "cache_hit": len(chunks) > 0,
            "errors": errors,
        }

    except Exception as exc:
        errors.append(f"check_chunk_cache failed: {exc}")
        logger.error("check_chunk_cache error: %s", exc)
        return {"retrieved_chunks": [], "cache_hit": False, "errors": errors}


# ---------------------------------------------------------------------------
# Node 4 — retrieve_chunks
# ---------------------------------------------------------------------------


async def retrieve_chunks(state: ChatState) -> dict[str, Any]:
    """Embed the user query and retrieve fresh chunks from pgvector.

    Merges newly retrieved chunks with any cached chunks already in
    ``retrieved_chunks``. Tracks the IDs of newly fetched chunks in
    ``new_chunk_ids`` so ``persist_turn`` can update the session cache.

    Args:
        state: Current chat state with user_message, company_id, and
            existing retrieved_chunks from cache.

    Returns:
        Partial state update with merged retrieved_chunks and new_chunk_ids.
    """
    user_message = state.get("user_message", "")
    company_id = uuid.UUID(state["company_id"])
    cached_chunks: list[ChunkResult] = state.get("retrieved_chunks", [])
    cached_ids: set[str] = {c.chunk_id for c in cached_chunks}
    errors = list(state.get("errors", []))

    if not user_message:
        return {
            "retrieved_chunks": cached_chunks,
            "new_chunk_ids": [],
            "errors": errors,
        }

    try:
        svc = EmbeddingsService()
        loop = asyncio.get_running_loop()
        query_embedding: list[float] = await loop.run_in_executor(
            None, svc.embed_text, user_message
        )

        async with async_session_factory() as db:
            repo = ChunkRepository(db)
            fresh_chunks = await repo.similarity_search(
                company_id=company_id,
                query_embedding=query_embedding,
                top_k=MAX_RETRIEVED_CHUNKS,
                source_types=EDGAR_SOURCE_TYPES,
            )

        # Keep only truly new chunks (not already in cache)
        new_chunks = [c for c in fresh_chunks if c.chunk_id not in cached_ids]
        new_chunk_ids = [c.chunk_id for c in new_chunks]

        # Merge: cached first (authoritative order), then new additions
        merged = cached_chunks + new_chunks

        logger.info(
            "retrieve_chunks: %d fresh, %d cached, %d merged",
            len(new_chunks),
            len(cached_chunks),
            len(merged),
        )
        return {
            "retrieved_chunks": merged,
            "new_chunk_ids": new_chunk_ids,
            "errors": errors,
        }

    except Exception as exc:
        errors.append(f"retrieve_chunks failed: {exc}")
        logger.error("retrieve_chunks error: %s", exc)
        return {
            "retrieved_chunks": cached_chunks,
            "new_chunk_ids": [],
            "errors": errors,
        }


# ---------------------------------------------------------------------------
# Node 5 — generate_response
# ---------------------------------------------------------------------------


async def generate_response(state: ChatState) -> dict[str, Any]:
    """Generate the assistant's response using Bedrock Claude Sonnet.

    Builds a prompt from:
    - Company context banner
    - LLM context window (rolling summary + last 10 messages)
    - Retrieved source chunks
    - The current user message

    Runs the synchronous boto3 call off the event loop via
    ``run_in_executor`` to avoid blocking.

    Args:
        state: Current chat state with llm_context, retrieved_chunks,
            user_message, ticker, and company_name.

    Returns:
        Partial state update with response text and citations.
    """
    user_message = state.get("user_message", "")
    ticker = state["ticker"]
    company_name = state.get("company_name", ticker)
    llm_context: list[ChatMessage] = state.get("llm_context", [])
    chunks: list[ChunkResult] = state.get("retrieved_chunks", [])
    errors = list(state.get("errors", []))
    settings = get_settings()

    # Build the source block
    source_block = (
        _format_chunks_for_prompt(chunks)
        if chunks
        else "(No source documents available.)"
    )
    conversation_block = _format_messages_for_prompt(llm_context) if llm_context else ""

    system_prompt = (
        f"You are an expert buy-side equity analyst assistant discussing "
        f"{company_name} ({ticker}) with an analyst. "
        "Answer questions using the provided source documents. "
        "Cite sources by referencing the numbered excerpt (e.g. '[1]', '[2]'). "
        "If the answer is not in the provided sources, say so clearly — "
        "do not speculate or hallucinate facts. "
        "Be concise, professional, and data-driven."
    )

    prompt = f"""=== CONVERSATION HISTORY ===
{conversation_block}

=== SOURCE DOCUMENTS ===
{source_block}

=== CURRENT QUESTION ===
USER: {user_message}

Please provide a thorough, citation-backed answer. Reference source excerpts by number where applicable."""

    try:
        client = BedrockClient(model_id=settings.bedrock_chat_model_id)
        loop = asyncio.get_running_loop()
        response_text: str = await loop.run_in_executor(
            None,
            lambda: client.invoke(
                prompt=prompt,
                model_id=settings.bedrock_chat_model_id,
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.2,
            ),
        )

        citations = _build_citations(chunks)

        logger.info(
            "generate_response: %s — %d words, %d citations",
            ticker,
            len(response_text.split()),
            len(citations),
        )
        return {
            "response": response_text,
            "citations": citations,
            "errors": errors,
        }

    except Exception as exc:
        errors.append(f"generate_response failed: {exc}")
        logger.error("generate_response error for %s: %s", ticker, exc)
        fallback = (
            f"I was unable to generate a response for your question about "
            f"{company_name} ({ticker}) due to a temporary error. "
            "Please try again."
        )
        return {"response": fallback, "citations": [], "errors": errors}


# ---------------------------------------------------------------------------
# Node 6 — generate_followups
# ---------------------------------------------------------------------------


async def generate_followups(state: ChatState) -> dict[str, Any]:
    """Generate 3 follow-up question chips using Claude Haiku.

    Inexpensive post-response step. Falls back to an empty list
    on error so the UI simply omits the chips rather than failing.

    Args:
        state: Current chat state with response, user_message, ticker.

    Returns:
        Partial state update with suggested_followups list.
    """
    response = state.get("response", "")
    user_message = state.get("user_message", "")
    ticker = state["ticker"]
    company_name = state.get("company_name", ticker)
    errors = list(state.get("errors", []))
    settings = get_settings()

    if not response:
        return {"suggested_followups": [], "errors": errors}

    prompt = f"""Based on this analyst conversation about {company_name} ({ticker}), suggest 3 follow-up questions.

User asked: "{user_message}"
Assistant answered: "{response[:500]}"

Return JSON only:
{{"questions": ["<question 1>", "<question 2>", "<question 3>"]}}

Questions should be specific, actionable, and under 15 words each."""

    try:
        client = BedrockClient(model_id=settings.bedrock_followup_model_id)
        loop = asyncio.get_running_loop()
        result: dict[str, Any] = await loop.run_in_executor(
            None,
            lambda: client.invoke_with_json(
                prompt=prompt,
                model_id=settings.bedrock_followup_model_id,
                max_tokens=300,
                temperature=0.3,
            ),
        )
        questions = result.get("questions", [])
        if not isinstance(questions, list):
            questions = []
        questions = [q for q in questions if isinstance(q, str)][:3]

        logger.info("generate_followups: %s — %d chips", ticker, len(questions))
        return {"suggested_followups": questions, "errors": errors}

    except Exception as exc:
        errors.append(f"generate_followups failed: {exc}")
        logger.error("generate_followups error: %s", exc)
        return {"suggested_followups": [], "errors": errors}


# ---------------------------------------------------------------------------
# Node 7 — persist_turn
# ---------------------------------------------------------------------------


async def persist_turn(state: ChatState) -> dict[str, Any]:
    """Append the current user+assistant turn to the session and update the chunk cache.

    Serialises both messages to JSONB-compatible dicts and calls
    ``ChatRepository.append_messages``. Then merges any newly retrieved
    chunk IDs into the session cache via ``update_chunk_cache``.

    Args:
        state: Current chat state with session_id, user_message, response,
            citations, suggested_followups, and new_chunk_ids.

    Returns:
        Empty state update (side-effects only — session DB row updated).
    """
    session_id_str = state.get("session_id", "")
    user_message = state.get("user_message", "")
    response = state.get("response", "")
    citations: list[Citation] = state.get("citations", [])
    suggested_followups: list[str] = state.get("suggested_followups", [])
    new_chunk_ids: list[str] = state.get("new_chunk_ids", [])
    messages: list[ChatMessage] = state.get("messages", [])
    errors = list(state.get("errors", []))

    if not session_id_str:
        errors.append("persist_turn: session_id missing — cannot persist")
        return {"errors": errors}

    try:
        session_id = uuid.UUID(session_id_str)
        turn_index = len(messages)  # next index in the existing list

        now = _now_iso()
        user_msg_dict: dict[str, Any] = {
            "role": "user",
            "content": user_message,
            "citations": [],
            "turn_index": turn_index,
            "created_at": now,
        }
        assistant_msg_dict: dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "citations": [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "title": c.title,
                    "source_type": c.source_type,
                    "source_url": c.source_url,
                    "excerpt": c.excerpt,
                }
                for c in citations
            ],
            "suggested_followups": suggested_followups,
            "turn_index": turn_index + 1,
            "created_at": now,
        }

        async with async_session_factory() as db:
            repo = ChatRepository(db)
            await repo.append_messages(session_id, user_msg_dict, assistant_msg_dict)
            if new_chunk_ids:
                await repo.update_chunk_cache(session_id, new_chunk_ids)
            await db.commit()

        logger.info(
            "persist_turn: session=%s turn_index=%d", session_id_str, turn_index
        )
        return {"errors": errors}

    except Exception as exc:
        errors.append(f"persist_turn failed: {exc}")
        logger.error("persist_turn error: %s", exc)
        return {"errors": errors}


# ---------------------------------------------------------------------------
# Node 8 — maybe_summarize
# ---------------------------------------------------------------------------


async def maybe_summarize(state: ChatState) -> dict[str, Any]:
    """Conditionally compress older messages into a rolling context summary.

    Triggered only when the session message count exceeds
    ``SUMMARY_THRESHOLD`` (20). Summarises messages from
    ``summary_through`` up to ``len(messages) - RAW_MESSAGE_WINDOW``,
    leaving the most recent ``RAW_MESSAGE_WINDOW`` messages as raw
    context for the next turn.

    Uses Claude Haiku (cost-optimised). Persists the new summary and
    updated ``summary_through`` index to the database.

    Args:
        state: Current chat state with messages, summary_through,
            context_summary, session_id, ticker, and company_name.

    Returns:
        Partial state update with updated context_summary and
        summary_through (only when summarisation ran).
    """
    session_id_str = state.get("session_id", "")
    messages: list[ChatMessage] = state.get("messages", [])
    current_summary: str = state.get("context_summary", "")
    summary_through: int = state.get("summary_through", 0)
    ticker = state["ticker"]
    company_name = state.get("company_name", ticker)
    errors = list(state.get("errors", []))
    settings = get_settings()

    # Check threshold: total stored messages after this turn = len(messages) + 2
    # We approximate by checking the pre-turn count.
    total_after_turn = len(messages) + 2
    if total_after_turn <= SUMMARY_THRESHOLD:
        return {"errors": errors}

    # Determine which messages to summarise this run
    summarise_up_to = max(0, len(messages) - RAW_MESSAGE_WINDOW)
    if summarise_up_to <= summary_through:
        # Nothing new to summarise
        return {"errors": errors}

    messages_to_summarise = messages[summary_through:summarise_up_to]
    if not messages_to_summarise:
        return {"errors": errors}

    conversation_excerpt = _format_messages_for_prompt(messages_to_summarise)
    preamble = f"Previous summary:\n{current_summary}\n\n" if current_summary else ""

    prompt = f"""{preamble}Summarise the following conversation about {company_name} ({ticker}) in 2–4 sentences, preserving key facts, numbers, and conclusions that a follow-up question might need.

Conversation:
{conversation_excerpt}

Summary:"""

    try:
        client = BedrockClient(model_id=settings.bedrock_followup_model_id)
        loop = asyncio.get_running_loop()
        new_summary: str = await loop.run_in_executor(
            None,
            lambda: client.invoke(
                prompt=prompt,
                model_id=settings.bedrock_followup_model_id,
                max_tokens=400,
                temperature=0.0,
            ),
        )
        new_summary = new_summary.strip()

        # Persist to database
        if session_id_str:
            try:
                session_id = uuid.UUID(session_id_str)
                async with async_session_factory() as db:
                    repo = ChatRepository(db)
                    await repo.update_context_summary(
                        session_id=session_id,
                        summary=new_summary,
                        summary_through=summarise_up_to,
                    )
                    await db.commit()
            except Exception as db_exc:
                errors.append(f"maybe_summarize db persist failed: {db_exc}")
                logger.error("maybe_summarize db persist error: %s", db_exc)

        logger.info(
            "maybe_summarize: %s — summarised msgs %d–%d",
            ticker,
            summary_through,
            summarise_up_to,
        )
        return {
            "context_summary": new_summary,
            "summary_through": summarise_up_to,
            "errors": errors,
        }

    except Exception as exc:
        errors.append(f"maybe_summarize failed: {exc}")
        logger.error("maybe_summarize error: %s", exc)
        return {"errors": errors}


# ---------------------------------------------------------------------------
# Node 9 — handle_errors
# ---------------------------------------------------------------------------


def handle_errors(state: ChatState) -> dict[str, Any]:
    """Log accumulated errors from the chat pipeline.

    Args:
        state: Current state with errors list.

    Returns:
        Empty state update (terminal node).
    """
    errors = state.get("errors", [])
    ticker = state.get("ticker", "unknown")
    session_id = state.get("session_id", "unknown")

    if errors:
        for error in errors:
            logger.error("ChatGraph error [%s/%s]: %s", ticker, session_id, error)
    else:
        logger.info(
            "ChatGraph completed successfully [%s] session=%s",
            ticker,
            session_id,
        )

    return {}
