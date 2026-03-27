"""BriefGraph node functions — top-level imports kept at module level for testability.

Each node receives the full BriefState and returns a partial state update dict.
Errors are accumulated in state['errors'] and never abort the pipeline — a
missing section degrades gracefully rather than producing no brief at all.

Node execution order
--------------------
retrieve_chunks
    └─ (parallel fan-out via Send)
        ├─ build_snapshot
        ├─ build_what_changed
        ├─ build_risk_flags
        ├─ build_sentiment
        └─ build_sources
    └─ (fan-in) assemble_sections
        └─ build_executive_summary
            └─ build_suggested_followups
                └─ store_brief
                    └─ handle_errors → END
"""

import asyncio
import json
import logging
import uuid
from decimal import Decimal
from typing import Any

from alphawatch.agents.state import (
    BriefSectionData,
    BriefState,
    ChunkResult,
    RiskFlagItem,
)
from alphawatch.config import get_settings
from alphawatch.database import async_session_factory
from alphawatch.repositories.briefs import BriefRepository
from alphawatch.repositories.chunks import ChunkRepository
from alphawatch.repositories.financial import FinancialSnapshotRepository
from alphawatch.repositories.sentiment import SentimentRepository
from alphawatch.services.bedrock import BedrockClient
from alphawatch.services.embeddings import EmbeddingsService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section ordering constants
# ---------------------------------------------------------------------------
ORDER_SNAPSHOT = 1
ORDER_WHAT_CHANGED = 2
ORDER_RISK_FLAGS = 3
ORDER_SENTIMENT = 4
ORDER_SOURCES = 5
ORDER_EXECUTIVE_SUMMARY = 6
ORDER_SUGGESTED_FOLLOWUPS = 7

# Source types that belong in the RAG index (news articles excluded)
EDGAR_SOURCE_TYPES = ["edgar_10k", "edgar_10q", "edgar_8k"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decimal_default(obj: Any) -> Any:
    """JSON serialiser fallback that converts Decimal to float.

    Args:
        obj: Object that the default JSON encoder cannot serialise.

    Returns:
        Float representation for Decimal; raises TypeError for all others.

    Raises:
        TypeError: If ``obj`` is not a Decimal.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def _truncate_chunks_for_prompt(
    chunks: list[ChunkResult], max_chars: int = 12_000
) -> str:
    """Format retrieved chunks into a prompt-safe string.

    Chunks are included in descending similarity order until the cumulative
    character count reaches ``max_chars``.

    Args:
        chunks: Ordered list of ChunkResult objects.
        max_chars: Maximum total characters to include.

    Returns:
        Formatted string with chunk index, title, and content.
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


def _chunk_citations(chunks: list[ChunkResult]) -> list[dict[str, str]]:
    """Build a citation list from retrieved chunks.

    Args:
        chunks: Retrieved chunks used as sources.

    Returns:
        List of dicts with chunk_id, title, source_type, source_url.
    """
    seen: set[str] = set()
    citations: list[dict[str, str]] = []
    for chunk in chunks:
        key = chunk.document_id
        if key not in seen:
            seen.add(key)
            citations.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "title": chunk.title,
                    "source_type": chunk.source_type,
                    "source_url": chunk.source_url,
                }
            )
    return citations


# ---------------------------------------------------------------------------
# Node 1 — retrieve_chunks
# ---------------------------------------------------------------------------


async def retrieve_chunks(state: BriefState) -> dict[str, Any]:
    """Embed the company ticker as a broad query and retrieve top-k chunks.

    Uses Titan Embeddings v2 to embed a broad "company overview" query,
    then retrieves the top-8 most similar chunks from pgvector restricted
    to EDGAR source types (news articles are excluded from RAG).

    Args:
        state: Current brief state with company_id and ticker.

    Returns:
        Partial state update with retrieved_chunks list.
    """
    ticker = state["ticker"]
    company_id = uuid.UUID(state["company_id"])
    company_name = state.get("company_name", ticker)
    query_text = state.get("query_text") or (
        f"{company_name} ({ticker}) business overview financials risks"
    )
    errors = list(state.get("errors", []))

    try:
        svc = EmbeddingsService()
        loop = asyncio.get_running_loop()
        query_embedding: list[float] = await loop.run_in_executor(
            None, svc.embed_text, query_text
        )

        async with async_session_factory() as session:  # type: ignore[attr-defined]
            repo = ChunkRepository(session)
            chunks = await repo.similarity_search(
                company_id=company_id,
                query_embedding=query_embedding,
                top_k=8,
                source_types=EDGAR_SOURCE_TYPES,
            )

        logger.info("retrieve_chunks: %s retrieved %d chunks", ticker, len(chunks))
        return {"retrieved_chunks": chunks, "errors": errors}

    except Exception as exc:
        errors.append(f"retrieve_chunks failed: {exc}")
        logger.error("retrieve_chunks error for %s: %s", ticker, exc)
        return {"retrieved_chunks": [], "errors": errors}


# ---------------------------------------------------------------------------
# Node 2 — build_snapshot
# ---------------------------------------------------------------------------


async def build_snapshot(state: BriefState) -> dict[str, Any]:
    """Build the financial snapshot section from the latest stored snapshot.

    This section is purely data-driven — no LLM involved. Pulls the most
    recent FinancialSnapshot row from the database and formats it as a
    structured dict.

    Args:
        state: Current brief state with company_id.

    Returns:
        Partial state update with snapshot_section BriefSectionData.
    """
    company_id = uuid.UUID(state["company_id"])
    ticker = state["ticker"]
    errors = list(state.get("errors", []))

    try:
        async with async_session_factory() as session:  # type: ignore[attr-defined]
            repo = FinancialSnapshotRepository(session)
            snapshot = await repo.get_latest(company_id)

        if snapshot is None:
            content: dict[str, Any] = {
                "available": False,
                "message": "No financial snapshot available yet.",
            }
        else:
            content = {
                "available": True,
                "snapshot_date": str(snapshot.snapshot_date),
                "price": float(snapshot.price) if snapshot.price is not None else None,
                "price_change_pct": (
                    float(snapshot.price_change_pct)
                    if snapshot.price_change_pct is not None
                    else None
                ),
                "market_cap": snapshot.market_cap,
                "pe_ratio": (
                    float(snapshot.pe_ratio) if snapshot.pe_ratio is not None else None
                ),
                "debt_to_equity": (
                    float(snapshot.debt_to_equity)
                    if snapshot.debt_to_equity is not None
                    else None
                ),
                "analyst_rating": snapshot.analyst_rating,
            }

        section = BriefSectionData(
            section_type="snapshot",
            section_order=ORDER_SNAPSHOT,
            content=content,
        )
        logger.info("build_snapshot: %s complete", ticker)
        return {"snapshot_section": section, "errors": errors}

    except Exception as exc:
        errors.append(f"build_snapshot failed: {exc}")
        logger.error("build_snapshot error for %s: %s", ticker, exc)
        fallback = BriefSectionData(
            section_type="snapshot",
            section_order=ORDER_SNAPSHOT,
            content={"available": False, "message": str(exc)},
        )
        return {"snapshot_section": fallback, "errors": errors}


# ---------------------------------------------------------------------------
# Node 3 — build_what_changed
# ---------------------------------------------------------------------------


async def build_what_changed(state: BriefState) -> dict[str, Any]:
    """Build the 'What Changed' section from data-driven snapshot diffs.

    Compares the two most recent FinancialSnapshots to produce a list of
    material changes. No LLM is used — this eliminates hallucination risk
    in the highest-signal brief section.

    Args:
        state: Current brief state with company_id.

    Returns:
        Partial state update with what_changed_section BriefSectionData.
    """
    company_id = uuid.UUID(state["company_id"])
    ticker = state["ticker"]
    errors = list(state.get("errors", []))

    try:
        async with async_session_factory() as session:  # type: ignore[attr-defined]
            repo = FinancialSnapshotRepository(session)
            snapshots = await repo.list_for_company(company_id, limit=2)

        changes: list[dict[str, Any]] = []

        if len(snapshots) >= 2:
            current, previous = snapshots[0], snapshots[1]

            def _pct_change(curr: Any, prev: Any) -> float | None:
                if curr is None or prev is None or float(prev) == 0:
                    return None
                return round((float(curr) - float(prev)) / abs(float(prev)) * 100, 2)

            def _delta(label: str, curr: Any, prev: Any, unit: str = "") -> None:
                if curr is None and prev is None:
                    return
                pct = _pct_change(curr, prev)
                if pct is not None and abs(pct) >= 0.5:  # threshold: 0.5%
                    changes.append(
                        {
                            "metric": label,
                            "previous": float(prev) if prev is not None else None,
                            "current": float(curr) if curr is not None else None,
                            "change_pct": pct,
                            "unit": unit,
                            "from_date": str(previous.snapshot_date),
                            "to_date": str(current.snapshot_date),
                        }
                    )

            _delta("Price", current.price, previous.price, "USD")
            _delta("Market Cap", current.market_cap, previous.market_cap, "USD")
            _delta("P/E Ratio", current.pe_ratio, previous.pe_ratio)
            _delta("Debt / Equity", current.debt_to_equity, previous.debt_to_equity)

            # Analyst rating change (non-numeric)
            if (
                current.analyst_rating
                and previous.analyst_rating
                and current.analyst_rating != previous.analyst_rating
            ):
                changes.append(
                    {
                        "metric": "Analyst Rating",
                        "previous": previous.analyst_rating,
                        "current": current.analyst_rating,
                        "change_pct": None,
                        "unit": "",
                        "from_date": str(previous.snapshot_date),
                        "to_date": str(current.snapshot_date),
                    }
                )

            content: dict[str, Any] = {
                "has_changes": bool(changes),
                "changes": changes,
                "from_date": str(previous.snapshot_date),
                "to_date": str(current.snapshot_date),
            }
        elif len(snapshots) == 1:
            content = {
                "has_changes": False,
                "changes": [],
                "message": "Only one snapshot available; no comparison possible.",
                "to_date": str(snapshots[0].snapshot_date),
            }
        else:
            content = {
                "has_changes": False,
                "changes": [],
                "message": "No financial snapshots available yet.",
            }

        section = BriefSectionData(
            section_type="what_changed",
            section_order=ORDER_WHAT_CHANGED,
            content=content,
        )
        logger.info(
            "build_what_changed: %s — %d changes detected", ticker, len(changes)
        )
        return {"what_changed_section": section, "errors": errors}

    except Exception as exc:
        errors.append(f"build_what_changed failed: {exc}")
        logger.error("build_what_changed error for %s: %s", ticker, exc)
        fallback = BriefSectionData(
            section_type="what_changed",
            section_order=ORDER_WHAT_CHANGED,
            content={"has_changes": False, "changes": [], "message": str(exc)},
        )
        return {"what_changed_section": fallback, "errors": errors}


# ---------------------------------------------------------------------------
# Node 4 — build_risk_flags
# ---------------------------------------------------------------------------


async def build_risk_flags(state: BriefState) -> dict[str, Any]:
    """Identify risk flags from retrieved chunks using Bedrock Claude.

    Runs asynchronously off the event loop via run_in_executor. Returns
    a structured list of RiskFlagItem objects with severity, category, and
    source chunk IDs. Falls back to an empty list on error.

    Args:
        state: Current brief state with retrieved_chunks.

    Returns:
        Partial state update with risk_flags_section BriefSectionData.
    """
    ticker = state["ticker"]
    company_name = state.get("company_name", ticker)
    chunks: list[ChunkResult] = state.get("retrieved_chunks", [])
    errors = list(state.get("errors", []))
    settings = get_settings()

    if not chunks:
        section = BriefSectionData(
            section_type="risk_flags",
            section_order=ORDER_RISK_FLAGS,
            content={
                "flags": [],
                "message": "No source data available for risk analysis.",
            },
        )
        return {"risk_flags_section": section, "errors": errors}

    chunk_text = _truncate_chunks_for_prompt(chunks, max_chars=8_000)
    chunk_index_map = {str(i + 1): c.chunk_id for i, c in enumerate(chunks)}

    system_prompt = (
        "You are a buy-side financial analyst. Identify material risk factors "
        "from SEC filings and financial data. Be concise, specific, and grounded "
        "in the provided source text. Do not speculate beyond what is stated."
    )

    prompt = f"""Analyze the following excerpts from SEC filings for {company_name} ({ticker}) and identify up to 5 material risk factors.

Source excerpts:
{chunk_text}

Return a JSON object with a "flags" array. Each flag must have:
- "severity": one of "high", "medium", "low"
- "category": one of "financial", "regulatory", "operational", "market", "legal", "strategic"
- "description": 1–2 sentence description grounded in the source text
- "source_chunk_indices": array of source excerpt numbers (e.g. [1, 3]) that support this flag

Example:
{{
  "flags": [
    {{
      "severity": "high",
      "category": "regulatory",
      "description": "The company faces ongoing SEC investigation into revenue recognition practices disclosed in the 10-K.",
      "source_chunk_indices": [2]
    }}
  ]
}}

Return only the JSON object, no other text.
"""

    try:
        client = BedrockClient(model_id=settings.bedrock_brief_model_id)
        loop = asyncio.get_running_loop()
        result: dict[str, Any] = await loop.run_in_executor(
            None,
            lambda: client.invoke_with_json(
                prompt=prompt,
                system_prompt=system_prompt,
                model_id=settings.bedrock_brief_model_id,
                max_tokens=1500,
                temperature=0.0,
            ),
        )

        raw_flags = result.get("flags", [])
        flags: list[dict[str, Any]] = []
        for rf in raw_flags:
            severity = rf.get("severity", "low")
            if severity not in {"high", "medium", "low"}:
                severity = "low"
            category = rf.get("category", "operational")
            description = rf.get("description", "")
            indices = rf.get("source_chunk_indices", [])
            source_chunk_ids = [
                chunk_index_map[str(idx)]
                for idx in indices
                if str(idx) in chunk_index_map
            ]
            flags.append(
                {
                    "severity": severity,
                    "category": category,
                    "description": description,
                    "source_chunk_ids": source_chunk_ids,
                }
            )

        # Sort by severity priority
        severity_order = {"high": 0, "medium": 1, "low": 2}
        flags.sort(key=lambda f: severity_order.get(f["severity"], 3))

        content: dict[str, Any] = {"flags": flags}
        logger.info("build_risk_flags: %s — %d flags identified", ticker, len(flags))

    except Exception as exc:
        errors.append(f"build_risk_flags failed: {exc}")
        logger.error("build_risk_flags error for %s: %s", ticker, exc)
        content = {"flags": [], "message": str(exc)}

    section = BriefSectionData(
        section_type="risk_flags",
        section_order=ORDER_RISK_FLAGS,
        content=content,
    )
    return {"risk_flags_section": section, "errors": errors}


# ---------------------------------------------------------------------------
# Node 5 — build_sentiment
# ---------------------------------------------------------------------------


async def build_sentiment(state: BriefState) -> dict[str, Any]:
    """Build the sentiment section from stored SentimentRecord aggregates.

    Pulls pre-computed sentiment scores from the database (populated by
    SentimentGraph) rather than re-scoring. Returns average scores by
    source type and an overall composite.

    Args:
        state: Current brief state with company_id.

    Returns:
        Partial state update with sentiment_section BriefSectionData.
    """
    company_id = uuid.UUID(state["company_id"])
    ticker = state["ticker"]
    errors = list(state.get("errors", []))

    try:
        async with async_session_factory() as session:  # type: ignore[attr-defined]
            repo = SentimentRepository(session)
            overall = await repo.get_average_sentiment(company_id, days=7)
            by_source = await repo.get_sentiment_by_source(company_id, days=7)
            trend = await repo.get_sentiment_trend(company_id, days=30)

        def _label(score: float | None) -> str:
            if score is None:
                return "neutral"
            if score >= 30:
                return "positive"
            if score <= -30:
                return "negative"
            return "neutral"

        content: dict[str, Any] = {
            "available": overall is not None,
            "overall_score": round(overall, 1) if overall is not None else None,
            "overall_label": _label(overall),
            "by_source": {src: round(score, 1) for src, score in by_source.items()},
            "trend_30d": [
                {"date": date_str, "score": round(score, 1)}
                for date_str, score in trend
            ],
            "window_days": 7,
        }

        logger.info(
            "build_sentiment: %s — overall=%.1f (%s)",
            ticker,
            overall or 0.0,
            _label(overall),
        )

    except Exception as exc:
        errors.append(f"build_sentiment failed: {exc}")
        logger.error("build_sentiment error for %s: %s", ticker, exc)
        content = {
            "available": False,
            "overall_score": None,
            "overall_label": "neutral",
            "by_source": {},
            "trend_30d": [],
            "window_days": 7,
            "message": str(exc),
        }

    section = BriefSectionData(
        section_type="sentiment",
        section_order=ORDER_SENTIMENT,
        content=content,
    )
    return {"sentiment_section": section, "errors": errors}


# ---------------------------------------------------------------------------
# Node 6 — build_sources
# ---------------------------------------------------------------------------


def build_sources(state: BriefState) -> dict[str, Any]:
    """Build the sources section from retrieved chunks.

    Purely data-driven — no LLM call. Deduplicates by document_id to
    produce a clean list of source documents used in the brief.

    Args:
        state: Current brief state with retrieved_chunks.

    Returns:
        Partial state update with sources_section BriefSectionData.
    """
    chunks: list[ChunkResult] = state.get("retrieved_chunks", [])
    errors = list(state.get("errors", []))

    citations = _chunk_citations(chunks)
    content: dict[str, Any] = {
        "sources": citations,
        "total_chunks_retrieved": len(chunks),
        "total_documents": len(citations),
    }

    section = BriefSectionData(
        section_type="sources",
        section_order=ORDER_SOURCES,
        content=content,
    )
    logger.info(
        "build_sources: %s — %d unique documents from %d chunks",
        state["ticker"],
        len(citations),
        len(chunks),
    )
    return {"sources_section": section, "errors": errors}


# ---------------------------------------------------------------------------
# Node 7 (fan-in) — assemble_sections
# ---------------------------------------------------------------------------


def assemble_sections(state: BriefState) -> dict[str, Any]:
    """Collect all parallel section outputs into a single ordered list.

    This is the fan-in node that waits for all parallel section builders
    to complete before the sequential executive summary step.

    Args:
        state: Current brief state with all *_section fields populated.

    Returns:
        Partial state update with sections list ordered by section_order.
    """
    candidates: list[BriefSectionData | None] = [
        state.get("snapshot_section"),
        state.get("what_changed_section"),
        state.get("risk_flags_section"),
        state.get("sentiment_section"),
        state.get("sources_section"),
    ]
    sections = [s for s in candidates if s is not None]
    sections.sort(key=lambda s: s.section_order)

    logger.info(
        "assemble_sections: %s — %d sections assembled", state["ticker"], len(sections)
    )
    return {"sections": sections}


# ---------------------------------------------------------------------------
# Node 8 — build_executive_summary
# ---------------------------------------------------------------------------


async def build_executive_summary(state: BriefState) -> dict[str, Any]:
    """Synthesize an executive summary from the already-built sections.

    Runs LAST among the content-generation nodes to guarantee it can
    only summarise information that was surfaced in preceding sections.
    Every claim in the summary must be traceable to a retrieved chunk.

    Args:
        state: Current brief state with all sections and retrieved_chunks.

    Returns:
        Partial state update with executive_summary_section BriefSectionData.
    """
    ticker = state["ticker"]
    company_name = state.get("company_name", ticker)
    sections: list[BriefSectionData] = state.get("sections", [])
    chunks: list[ChunkResult] = state.get("retrieved_chunks", [])
    errors = list(state.get("errors", []))
    settings = get_settings()

    # Build a compact context from sections (no raw chunks needed here)
    section_summaries: list[str] = []
    for s in sections:
        if s.section_type == "snapshot" and s.content.get("available"):
            c = s.content
            section_summaries.append(
                f"FINANCIAL SNAPSHOT (as of {c.get('snapshot_date', 'N/A')}): "
                f"Price=${c.get('price')}, Market Cap=${c.get('market_cap')}, "
                f"P/E={c.get('pe_ratio')}, D/E={c.get('debt_to_equity')}, "
                f"Rating={c.get('analyst_rating')}"
            )
        elif s.section_type == "what_changed":
            changes = s.content.get("changes", [])
            if changes:
                change_lines = "; ".join(
                    f"{ch['metric']}: {ch.get('previous')} → {ch.get('current')} "
                    f"({ch.get('change_pct', 'N/A')}%)"
                    for ch in changes
                )
                section_summaries.append(f"WHAT CHANGED: {change_lines}")
            else:
                section_summaries.append("WHAT CHANGED: No material changes detected.")
        elif s.section_type == "risk_flags":
            flags = s.content.get("flags", [])
            if flags:
                flag_lines = "; ".join(
                    f"[{f['severity'].upper()}] {f['category']}: {f['description']}"
                    for f in flags
                )
                section_summaries.append(f"RISK FLAGS: {flag_lines}")
            else:
                section_summaries.append("RISK FLAGS: No material risks identified.")
        elif s.section_type == "sentiment":
            if s.content.get("available"):
                section_summaries.append(
                    f"SENTIMENT (7d): {s.content.get('overall_label', 'neutral').upper()} "
                    f"(score={s.content.get('overall_score')})"
                )
            else:
                section_summaries.append("SENTIMENT: Insufficient data.")

    context_block = "\n".join(section_summaries)
    chunk_text = _truncate_chunks_for_prompt(chunks, max_chars=5_000)

    system_prompt = (
        "You are a senior buy-side equity analyst. Write a concise, professional "
        "executive summary for an analyst brief. Every factual claim must be supported "
        "by the data provided in the sections and source excerpts below. "
        "Do not introduce information not present in the provided data. "
        "Write in third person, professional tone, 150–250 words."
    )

    prompt = f"""Write an executive summary for {company_name} ({ticker}) based solely on the following data.

=== SECTION DATA ===
{context_block}

=== SOURCE EXCERPTS ===
{chunk_text}

Return a JSON object with:
- "summary": the executive summary text (150–250 words)
- "key_points": array of 3–5 bullet-point strings highlighting the most material findings
- "source_chunk_ids": array of chunk IDs from the source excerpts that directly support claims in the summary

Return only the JSON object, no other text.
"""

    chunk_id_list = [c.chunk_id for c in chunks]

    try:
        client = BedrockClient(model_id=settings.bedrock_brief_model_id)
        loop = asyncio.get_running_loop()
        result: dict[str, Any] = await loop.run_in_executor(
            None,
            lambda: client.invoke_with_json(
                prompt=prompt,
                system_prompt=system_prompt,
                model_id=settings.bedrock_brief_model_id,
                max_tokens=2000,
                temperature=0.2,
            ),
        )

        summary_text = result.get("summary", "")
        key_points = result.get("key_points", [])
        cited_ids = [
            cid for cid in result.get("source_chunk_ids", []) if cid in chunk_id_list
        ]

        content: dict[str, Any] = {
            "summary": summary_text,
            "key_points": key_points,
            "cited_chunk_ids": cited_ids,
        }
        logger.info(
            "build_executive_summary: %s — %d words", ticker, len(summary_text.split())
        )

    except Exception as exc:
        errors.append(f"build_executive_summary failed: {exc}")
        logger.error("build_executive_summary error for %s: %s", ticker, exc)
        content = {
            "summary": (
                f"Executive summary unavailable for {company_name} due to a generation error."
            ),
            "key_points": [],
            "cited_chunk_ids": [],
            "message": str(exc),
        }

    section = BriefSectionData(
        section_type="executive_summary",
        section_order=ORDER_EXECUTIVE_SUMMARY,
        content=content,
    )
    return {"executive_summary_section": section, "errors": errors}


# ---------------------------------------------------------------------------
# Node 9 — build_suggested_followups
# ---------------------------------------------------------------------------


async def build_suggested_followups(state: BriefState) -> dict[str, Any]:
    """Generate suggested follow-up questions for the chat interface.

    Uses Claude Haiku (cost-optimised) to generate 3–5 contextually
    relevant follow-up questions based on the executive summary and
    risk flags. Stored as a brief section so the UI can display them
    as clickable chips.

    Args:
        state: Current brief state with executive_summary_section and
            risk_flags_section.

    Returns:
        Partial state update with suggested_followups_section BriefSectionData.
    """
    ticker = state["ticker"]
    company_name = state.get("company_name", ticker)
    errors = list(state.get("errors", []))
    settings = get_settings()

    exec_section: BriefSectionData | None = state.get("executive_summary_section")
    risk_section: BriefSectionData | None = state.get("risk_flags_section")

    summary_text = ""
    if exec_section:
        summary_text = exec_section.content.get("summary", "")

    risk_flags_text = ""
    if risk_section:
        flags = risk_section.content.get("flags", [])
        risk_flags_text = "; ".join(
            f"[{f['severity']}] {f['description']}" for f in flags[:3]
        )

    prompt = f"""Based on the following analyst brief for {company_name} ({ticker}), generate 4 insightful follow-up questions a buy-side analyst might ask to dig deeper.

Executive Summary:
{summary_text[:1000]}

Top Risk Flags:
{risk_flags_text}

Return a JSON object with:
- "questions": array of 4 question strings, each 10–20 words, starting with a verb or question word

Return only the JSON object.
"""

    try:
        client = BedrockClient(model_id=settings.bedrock_followup_model_id)
        loop = asyncio.get_running_loop()
        result: dict[str, Any] = await loop.run_in_executor(
            None,
            lambda: client.invoke_with_json(
                prompt=prompt,
                model_id=settings.bedrock_followup_model_id,
                max_tokens=500,
                temperature=0.3,
            ),
        )
        questions = result.get("questions", [])
        if not isinstance(questions, list):
            questions = []
        questions = [q for q in questions if isinstance(q, str)][:5]

        content: dict[str, Any] = {"questions": questions}
        logger.info(
            "build_suggested_followups: %s — %d questions", ticker, len(questions)
        )

    except Exception as exc:
        errors.append(f"build_suggested_followups failed: {exc}")
        logger.error("build_suggested_followups error for %s: %s", ticker, exc)
        content = {"questions": [], "message": str(exc)}

    section = BriefSectionData(
        section_type="suggested_followups",
        section_order=ORDER_SUGGESTED_FOLLOWUPS,
        content=content,
    )
    return {"suggested_followups_section": section, "errors": errors}


# ---------------------------------------------------------------------------
# Node 10 — store_brief
# ---------------------------------------------------------------------------


async def store_brief(state: BriefState) -> dict[str, Any]:
    """Persist the fully assembled brief and all sections to the database.

    Combines the parallel sections with the sequential summary and
    follow-ups into one ordered list, then bulk-inserts them.

    Args:
        state: Current brief state with all *_section fields populated.

    Returns:
        Partial state update with brief_id UUID string.
    """
    company_id = uuid.UUID(state["company_id"])
    user_id_str = state.get("user_id", "")
    ticker = state["ticker"]
    errors = list(state.get("errors", []))

    # Resolve user_id — fall back to a deterministic nil UUID for system runs
    try:
        user_id = uuid.UUID(user_id_str) if user_id_str else uuid.UUID(int=0)
    except ValueError:
        user_id = uuid.UUID(int=0)

    # Collect all sections
    all_sections: list[BriefSectionData] = list(state.get("sections", []))
    for attr in (
        "executive_summary_section",
        "suggested_followups_section",
    ):
        s: BriefSectionData | None = state.get(attr)
        if s is not None:
            all_sections.append(s)

    all_sections.sort(key=lambda s: s.section_order)

    try:
        session_id = uuid.uuid4()

        async with async_session_factory() as session:  # type: ignore[attr-defined]
            repo = BriefRepository(session)
            brief = await repo.create_brief(
                user_id=user_id,
                company_id=company_id,
                session_id=session_id,
            )
            await repo.bulk_create_sections(brief.id, all_sections)
            await session.commit()
            brief_id = str(brief.id)

        logger.info(
            "store_brief: %s — brief %s stored with %d sections",
            ticker,
            brief_id,
            len(all_sections),
        )
        return {"brief_id": brief_id, "errors": errors}

    except Exception as exc:
        errors.append(f"store_brief failed: {exc}")
        logger.error("store_brief error for %s: %s", ticker, exc)
        return {"brief_id": "", "errors": errors}


# ---------------------------------------------------------------------------
# Node 11 — handle_errors
# ---------------------------------------------------------------------------


def handle_errors(state: BriefState) -> dict[str, Any]:
    """Log accumulated errors from the brief generation pipeline.

    Args:
        state: Current state with errors list.

    Returns:
        Empty state update (terminal node).
    """
    errors = state.get("errors", [])
    ticker = state.get("ticker", "unknown")
    brief_id = state.get("brief_id", "")

    if errors:
        for error in errors:
            logger.error("BriefGraph error [%s]: %s", ticker, error)
    else:
        logger.info(
            "BriefGraph completed successfully [%s]: brief_id=%s", ticker, brief_id
        )

    return {}
