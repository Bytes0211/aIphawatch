"""Tests for BriefGraph: state types, node functions, graph, repositories, and integration."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from alphawatch.agents.state import (
    BaseState,
    BriefSectionData,
    BriefState,
    ChunkResult,
    RiskFlagItem,
)

# ---------------------------------------------------------------------------
# State type tests
# ---------------------------------------------------------------------------


class TestChunkResult:
    """Tests for ChunkResult dataclass."""

    def test_creation_minimal(self):
        chunk = ChunkResult(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="Apple reported strong earnings.",
            similarity=0.92,
            source_type="edgar_10k",
            source_url="https://example.com/filing",
            title="Apple 10-K 2025",
        )
        assert chunk.chunk_id == "chunk-1"
        assert chunk.similarity == 0.92
        assert chunk.metadata == {}

    def test_creation_with_metadata(self):
        chunk = ChunkResult(
            chunk_id="chunk-2",
            document_id="doc-2",
            content="Revenue grew 12%.",
            similarity=0.85,
            source_type="edgar_10q",
            source_url="https://example.com/10q",
            title="Apple 10-Q",
            metadata={"section": "MD&A", "page": 12},
        )
        assert chunk.metadata["section"] == "MD&A"
        assert chunk.metadata["page"] == 12


class TestRiskFlagItem:
    """Tests for RiskFlagItem dataclass."""

    def test_creation_minimal(self):
        flag = RiskFlagItem(
            severity="high",
            category="regulatory",
            description="SEC investigation ongoing.",
        )
        assert flag.severity == "high"
        assert flag.source_chunk_ids == []

    def test_creation_with_sources(self):
        flag = RiskFlagItem(
            severity="medium",
            category="financial",
            description="Debt levels rising.",
            source_chunk_ids=["chunk-1", "chunk-3"],
        )
        assert len(flag.source_chunk_ids) == 2


class TestBriefSectionData:
    """Tests for BriefSectionData dataclass."""

    def test_snapshot_section(self):
        section = BriefSectionData(
            section_type="snapshot",
            section_order=1,
            content={"price": 182.5, "pe_ratio": 28.4},
        )
        assert section.section_type == "snapshot"
        assert section.section_order == 1
        assert section.content["price"] == 182.5

    def test_executive_summary_section(self):
        section = BriefSectionData(
            section_type="executive_summary",
            section_order=6,
            content={"summary": "Apple delivered strong results.", "key_points": []},
        )
        assert section.section_type == "executive_summary"
        assert section.section_order == 6


class TestBriefState:
    """Tests for BriefState TypedDict."""

    def test_extends_base_state(self):
        state: BriefState = {
            "company_id": "c-1",
            "ticker": "AAPL",
        }
        assert state["ticker"] == "AAPL"
        assert state["company_id"] == "c-1"

    def test_full_state(self):
        chunk = ChunkResult(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="Test content.",
            similarity=0.9,
            source_type="edgar_10k",
            source_url="https://example.com",
            title="10-K",
        )
        section = BriefSectionData(
            section_type="snapshot",
            section_order=1,
            content={"available": True},
        )
        state: BriefState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "tenant_id": "t-1",
            "user_id": "u-1",
            "company_name": "Apple Inc.",
            "errors": [],
            "metadata": {},
            "retrieved_chunks": [chunk],
            "snapshot_section": section,
            "sections": [section],
            "brief_id": "b-1",
        }
        assert state["company_name"] == "Apple Inc."
        assert len(state["retrieved_chunks"]) == 1
        assert state["brief_id"] == "b-1"

    def test_optional_fields_absent(self):
        state: BriefState = {"company_id": "c-1", "ticker": "MSFT"}
        assert "retrieved_chunks" not in state
        assert "brief_id" not in state
        assert "force_regenerate" not in state


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestBriefNodeHelpers:
    """Tests for private helper functions in brief nodes."""

    def test_truncate_chunks_for_prompt(self):
        from alphawatch.agents.nodes.brief import _truncate_chunks_for_prompt

        chunks = [
            ChunkResult(
                chunk_id=f"c{i}",
                document_id=f"d{i}",
                content=f"Content block {i}",
                similarity=0.9 - i * 0.05,
                source_type="edgar_10k",
                source_url="https://example.com",
                title=f"Doc {i}",
            )
            for i in range(5)
        ]
        result = _truncate_chunks_for_prompt(chunks, max_chars=1000)
        assert "[1]" in result
        assert "Doc 0" in result

    def test_truncate_chunks_respects_max_chars(self):
        from alphawatch.agents.nodes.brief import _truncate_chunks_for_prompt

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="d1",
                content="x" * 500,
                similarity=0.9,
                source_type="edgar_10k",
                source_url="",
                title="Big doc",
            ),
            ChunkResult(
                chunk_id="c2",
                document_id="d2",
                content="y" * 500,
                similarity=0.85,
                source_type="edgar_10k",
                source_url="",
                title="Second big doc",
            ),
        ]
        result = _truncate_chunks_for_prompt(chunks, max_chars=600)
        assert "Second big doc" not in result

    def test_chunk_citations_deduplicates_by_document(self):
        from alphawatch.agents.nodes.brief import _chunk_citations

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="doc-shared",
                content="A",
                similarity=0.9,
                source_type="edgar_10k",
                source_url="https://example.com",
                title="Shared Doc",
            ),
            ChunkResult(
                chunk_id="c2",
                document_id="doc-shared",  # same doc_id
                content="B",
                similarity=0.85,
                source_type="edgar_10k",
                source_url="https://example.com",
                title="Shared Doc",
            ),
            ChunkResult(
                chunk_id="c3",
                document_id="doc-unique",
                content="C",
                similarity=0.80,
                source_type="edgar_10q",
                source_url="https://other.com",
                title="Unique Doc",
            ),
        ]
        citations = _chunk_citations(chunks)
        assert len(citations) == 2
        doc_ids = {c["document_id"] for c in citations}
        assert "doc-shared" in doc_ids
        assert "doc-unique" in doc_ids

    def test_chunk_citations_empty(self):
        from alphawatch.agents.nodes.brief import _chunk_citations

        assert _chunk_citations([]) == []

    def test_decimal_default_converts_decimal(self):
        from alphawatch.agents.nodes.brief import _decimal_default

        assert _decimal_default(Decimal("182.50")) == 182.50

    def test_decimal_default_raises_for_other_types(self):
        from alphawatch.agents.nodes.brief import _decimal_default

        with pytest.raises(TypeError):
            _decimal_default("not a decimal")


# ---------------------------------------------------------------------------
# Node: retrieve_chunks
# ---------------------------------------------------------------------------


class TestRetrieveChunks:
    """Tests for the retrieve_chunks node."""

    @pytest.mark.asyncio
    async def test_returns_chunks_on_success(self):
        from alphawatch.agents.nodes.brief import retrieve_chunks

        mock_chunk = ChunkResult(
            chunk_id="c1",
            document_id="d1",
            content="Apple revenue data",
            similarity=0.91,
            source_type="edgar_10k",
            source_url="https://example.com",
            title="Apple 10-K",
        )

        mock_embed_svc = Mock()
        mock_embed_svc.embed_text = Mock(return_value=[0.1] * 1536)

        mock_repo = AsyncMock()
        mock_repo.similarity_search = AsyncMock(return_value=[mock_chunk])

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.EmbeddingsService",
                return_value=mock_embed_svc,
            ),
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.ChunkRepository", return_value=mock_repo
            ),
        ):
            result = await retrieve_chunks(state)

        assert "retrieved_chunks" in result
        assert len(result["retrieved_chunks"]) == 1
        assert result["retrieved_chunks"][0].chunk_id == "c1"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        from alphawatch.agents.nodes.brief import retrieve_chunks

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.EmbeddingsService",
            side_effect=RuntimeError("Bedrock unavailable"),
        ):
            result = await retrieve_chunks(state)

        assert result["retrieved_chunks"] == []
        assert len(result["errors"]) == 1
        assert "retrieve_chunks failed" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_uses_custom_query_text(self):
        from alphawatch.agents.nodes.brief import retrieve_chunks

        captured_texts: list[str] = []

        mock_embed_svc = Mock()

        def capture_embed(text: str) -> list[float]:
            captured_texts.append(text)
            return [0.0] * 1536

        mock_embed_svc.embed_text = capture_embed

        mock_repo = AsyncMock()
        mock_repo.similarity_search = AsyncMock(return_value=[])
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "query_text": "Apple debt obligations covenant",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.EmbeddingsService",
                return_value=mock_embed_svc,
            ),
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.ChunkRepository", return_value=mock_repo
            ),
        ):
            await retrieve_chunks(state)

        assert captured_texts[0] == "Apple debt obligations covenant"


# ---------------------------------------------------------------------------
# Node: build_snapshot
# ---------------------------------------------------------------------------


class TestBuildSnapshot:
    """Tests for the build_snapshot node."""

    @pytest.mark.asyncio
    async def test_snapshot_available(self):
        from alphawatch.agents.nodes.brief import build_snapshot

        mock_snapshot = Mock()
        mock_snapshot.snapshot_date = "2026-03-20"
        mock_snapshot.price = Decimal("182.50")
        mock_snapshot.price_change_pct = Decimal("1.23")
        mock_snapshot.market_cap = 2_800_000_000_000
        mock_snapshot.pe_ratio = Decimal("28.4")
        mock_snapshot.debt_to_equity = Decimal("1.87")
        mock_snapshot.analyst_rating = "Strong Buy"

        mock_repo = AsyncMock()
        mock_repo.get_latest = AsyncMock(return_value=mock_snapshot)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.FinancialSnapshotRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_snapshot(state)

        section = result["snapshot_section"]
        assert section.section_type == "snapshot"
        assert section.section_order == 1
        assert section.content["available"] is True
        assert section.content["price"] == 182.50
        assert section.content["analyst_rating"] == "Strong Buy"

    @pytest.mark.asyncio
    async def test_snapshot_unavailable(self):
        from alphawatch.agents.nodes.brief import build_snapshot

        mock_repo = AsyncMock()
        mock_repo.get_latest = AsyncMock(return_value=None)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.FinancialSnapshotRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_snapshot(state)

        section = result["snapshot_section"]
        assert section.content["available"] is False
        assert "message" in section.content

    @pytest.mark.asyncio
    async def test_snapshot_handles_none_fields(self):
        from alphawatch.agents.nodes.brief import build_snapshot

        mock_snapshot = Mock()
        mock_snapshot.snapshot_date = "2026-03-20"
        mock_snapshot.price = None
        mock_snapshot.price_change_pct = None
        mock_snapshot.market_cap = None
        mock_snapshot.pe_ratio = None
        mock_snapshot.debt_to_equity = None
        mock_snapshot.analyst_rating = None

        mock_repo = AsyncMock()
        mock_repo.get_latest = AsyncMock(return_value=mock_snapshot)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.FinancialSnapshotRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_snapshot(state)

        section = result["snapshot_section"]
        assert section.content["available"] is True
        assert section.content["price"] is None

    @pytest.mark.asyncio
    async def test_snapshot_error_returns_fallback(self):
        from alphawatch.agents.nodes.brief import build_snapshot

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.async_session_factory",
            side_effect=RuntimeError("DB unreachable"),
        ):
            result = await build_snapshot(state)

        section = result["snapshot_section"]
        assert section.content["available"] is False
        assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Node: build_what_changed
# ---------------------------------------------------------------------------


class TestBuildWhatChanged:
    """Tests for the build_what_changed node."""

    @pytest.mark.asyncio
    async def test_detects_price_change(self):
        from alphawatch.agents.nodes.brief import build_what_changed

        snap_current = Mock()
        snap_current.snapshot_date = "2026-03-26"
        snap_current.price = Decimal("182.50")
        snap_current.market_cap = 2_800_000_000_000
        snap_current.pe_ratio = Decimal("29.0")
        snap_current.debt_to_equity = Decimal("1.87")
        snap_current.analyst_rating = "Strong Buy"

        snap_previous = Mock()
        snap_previous.snapshot_date = "2026-03-19"
        snap_previous.price = Decimal("170.00")
        snap_previous.market_cap = 2_600_000_000_000
        snap_previous.pe_ratio = Decimal("27.0")
        snap_previous.debt_to_equity = Decimal("1.87")
        snap_previous.analyst_rating = "Strong Buy"

        mock_repo = AsyncMock()
        mock_repo.list_for_company = AsyncMock(
            return_value=[snap_current, snap_previous]
        )
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.FinancialSnapshotRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_what_changed(state)

        section = result["what_changed_section"]
        assert section.section_type == "what_changed"
        assert section.section_order == 2
        assert section.content["has_changes"] is True
        metrics = {c["metric"] for c in section.content["changes"]}
        assert "Price" in metrics

    @pytest.mark.asyncio
    async def test_detects_analyst_rating_change(self):
        from alphawatch.agents.nodes.brief import build_what_changed

        snap_current = Mock()
        snap_current.snapshot_date = "2026-03-26"
        snap_current.price = Decimal("182.50")
        snap_current.market_cap = 2_800_000_000_000
        snap_current.pe_ratio = Decimal("28.4")
        snap_current.debt_to_equity = Decimal("1.87")
        snap_current.analyst_rating = "Buy"

        snap_previous = Mock()
        snap_previous.snapshot_date = "2026-03-19"
        snap_previous.price = Decimal("182.50")
        snap_previous.market_cap = 2_800_000_000_000
        snap_previous.pe_ratio = Decimal("28.4")
        snap_previous.debt_to_equity = Decimal("1.87")
        snap_previous.analyst_rating = "Hold"

        mock_repo = AsyncMock()
        mock_repo.list_for_company = AsyncMock(
            return_value=[snap_current, snap_previous]
        )
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.FinancialSnapshotRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_what_changed(state)

        changes = result["what_changed_section"].content["changes"]
        rating_changes = [c for c in changes if c["metric"] == "Analyst Rating"]
        assert len(rating_changes) == 1
        assert rating_changes[0]["previous"] == "Hold"
        assert rating_changes[0]["current"] == "Buy"

    @pytest.mark.asyncio
    async def test_no_snapshots_returns_message(self):
        from alphawatch.agents.nodes.brief import build_what_changed

        mock_repo = AsyncMock()
        mock_repo.list_for_company = AsyncMock(return_value=[])
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.FinancialSnapshotRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_what_changed(state)

        section = result["what_changed_section"]
        assert section.content["has_changes"] is False
        assert "message" in section.content

    @pytest.mark.asyncio
    async def test_single_snapshot_returns_message(self):
        from alphawatch.agents.nodes.brief import build_what_changed

        snap = Mock()
        snap.snapshot_date = "2026-03-26"
        snap.price = Decimal("182.50")
        snap.market_cap = None
        snap.pe_ratio = None
        snap.debt_to_equity = None
        snap.analyst_rating = None

        mock_repo = AsyncMock()
        mock_repo.list_for_company = AsyncMock(return_value=[snap])
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.FinancialSnapshotRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_what_changed(state)

        section = result["what_changed_section"]
        assert section.content["has_changes"] is False
        assert "Only one snapshot" in section.content.get("message", "")

    @pytest.mark.asyncio
    async def test_below_threshold_change_ignored(self):
        from alphawatch.agents.nodes.brief import build_what_changed

        snap_current = Mock()
        snap_current.snapshot_date = "2026-03-26"
        snap_current.price = Decimal("182.50")
        snap_current.market_cap = None
        snap_current.pe_ratio = None
        snap_current.debt_to_equity = None
        snap_current.analyst_rating = None

        snap_previous = Mock()
        snap_previous.snapshot_date = "2026-03-19"
        snap_previous.price = Decimal("182.40")  # < 0.5% change
        snap_previous.market_cap = None
        snap_previous.pe_ratio = None
        snap_previous.debt_to_equity = None
        snap_previous.analyst_rating = None

        mock_repo = AsyncMock()
        mock_repo.list_for_company = AsyncMock(
            return_value=[snap_current, snap_previous]
        )
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.FinancialSnapshotRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_what_changed(state)

        section = result["what_changed_section"]
        price_changes = [
            c for c in section.content["changes"] if c["metric"] == "Price"
        ]
        assert len(price_changes) == 0


# ---------------------------------------------------------------------------
# Node: build_risk_flags
# ---------------------------------------------------------------------------


class TestBuildRiskFlags:
    """Tests for the build_risk_flags node."""

    @pytest.mark.asyncio
    async def test_returns_flags_from_llm(self):
        from alphawatch.agents.nodes.brief import build_risk_flags

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="d1",
                content="The company faces regulatory scrutiny.",
                similarity=0.9,
                source_type="edgar_10k",
                source_url="",
                title="10-K",
            )
        ]

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={
                "flags": [
                    {
                        "severity": "high",
                        "category": "regulatory",
                        "description": "SEC investigation into accounting practices.",
                        "source_chunk_indices": [1],
                    }
                ]
            }
        )

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "retrieved_chunks": chunks,
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.BedrockClient", return_value=mock_client
        ):
            result = await build_risk_flags(state)

        section = result["risk_flags_section"]
        assert section.section_type == "risk_flags"
        assert section.section_order == 3
        assert len(section.content["flags"]) == 1
        assert section.content["flags"][0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_message(self):
        from alphawatch.agents.nodes.brief import build_risk_flags

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunks": [],
            "errors": [],
        }

        result = await build_risk_flags(state)
        section = result["risk_flags_section"]
        assert section.content["flags"] == []
        assert "message" in section.content

    @pytest.mark.asyncio
    async def test_invalid_severity_defaults_to_low(self):
        from alphawatch.agents.nodes.brief import build_risk_flags

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="d1",
                content="Some risk content.",
                similarity=0.9,
                source_type="edgar_10k",
                source_url="",
                title="10-K",
            )
        ]

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={
                "flags": [
                    {
                        "severity": "critical",  # invalid value
                        "category": "operational",
                        "description": "Supply chain disruption risk.",
                        "source_chunk_indices": [],
                    }
                ]
            }
        )

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunks": chunks,
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.BedrockClient", return_value=mock_client
        ):
            result = await build_risk_flags(state)

        section = result["risk_flags_section"]
        assert section.content["flags"][0]["severity"] == "low"

    @pytest.mark.asyncio
    async def test_flags_sorted_by_severity(self):
        from alphawatch.agents.nodes.brief import build_risk_flags

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="d1",
                content="Risk content.",
                similarity=0.9,
                source_type="edgar_10k",
                source_url="",
                title="10-K",
            )
        ]

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={
                "flags": [
                    {
                        "severity": "low",
                        "category": "market",
                        "description": "Low risk.",
                        "source_chunk_indices": [],
                    },
                    {
                        "severity": "high",
                        "category": "regulatory",
                        "description": "High risk.",
                        "source_chunk_indices": [],
                    },
                    {
                        "severity": "medium",
                        "category": "financial",
                        "description": "Medium risk.",
                        "source_chunk_indices": [],
                    },
                ]
            }
        )

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunks": chunks,
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.BedrockClient", return_value=mock_client
        ):
            result = await build_risk_flags(state)

        severities = [
            f["severity"] for f in result["risk_flags_section"].content["flags"]
        ]
        assert severities == ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_llm_error_returns_empty_flags(self):
        from alphawatch.agents.nodes.brief import build_risk_flags

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="d1",
                content="Risk content.",
                similarity=0.9,
                source_type="edgar_10k",
                source_url="",
                title="10-K",
            )
        ]

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(side_effect=RuntimeError("Bedrock error"))

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunks": chunks,
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.BedrockClient", return_value=mock_client
        ):
            result = await build_risk_flags(state)

        section = result["risk_flags_section"]
        assert section.content["flags"] == []
        assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Node: build_sentiment
# ---------------------------------------------------------------------------


class TestBuildSentiment:
    """Tests for the build_sentiment node."""

    @pytest.mark.asyncio
    async def test_sentiment_available(self):
        from alphawatch.agents.nodes.brief import build_sentiment

        mock_repo = AsyncMock()
        mock_repo.get_average_sentiment = AsyncMock(return_value=45.0)
        mock_repo.get_sentiment_by_source = AsyncMock(return_value={"news": 45.0})
        mock_repo.get_sentiment_trend = AsyncMock(
            return_value=[("2026-03-20", 40.0), ("2026-03-26", 50.0)]
        )
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.SentimentRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_sentiment(state)

        section = result["sentiment_section"]
        assert section.section_type == "sentiment"
        assert section.section_order == 4
        assert section.content["available"] is True
        assert section.content["overall_label"] == "positive"
        assert section.content["overall_score"] == 45.0
        assert len(section.content["trend_30d"]) == 2

    @pytest.mark.asyncio
    async def test_sentiment_unavailable_when_no_records(self):
        from alphawatch.agents.nodes.brief import build_sentiment

        mock_repo = AsyncMock()
        mock_repo.get_average_sentiment = AsyncMock(return_value=None)
        mock_repo.get_sentiment_by_source = AsyncMock(return_value={})
        mock_repo.get_sentiment_trend = AsyncMock(return_value=[])
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.SentimentRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_sentiment(state)

        section = result["sentiment_section"]
        assert section.content["available"] is False
        assert section.content["overall_score"] is None
        assert section.content["overall_label"] == "neutral"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "score,expected_label",
        [
            (75.0, "positive"),
            (30.0, "positive"),
            (29.9, "neutral"),
            (0.0, "neutral"),
            (-29.9, "neutral"),
            (-30.0, "negative"),
            (-80.0, "negative"),
        ],
    )
    async def test_sentiment_label_thresholds(self, score: float, expected_label: str):
        from alphawatch.agents.nodes.brief import build_sentiment

        mock_repo = AsyncMock()
        mock_repo.get_average_sentiment = AsyncMock(return_value=score)
        mock_repo.get_sentiment_by_source = AsyncMock(return_value={})
        mock_repo.get_sentiment_trend = AsyncMock(return_value=[])
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.SentimentRepository",
                return_value=mock_repo,
            ),
        ):
            result = await build_sentiment(state)

        assert result["sentiment_section"].content["overall_label"] == expected_label

    @pytest.mark.asyncio
    async def test_sentiment_error_returns_fallback(self):
        from alphawatch.agents.nodes.brief import build_sentiment

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.async_session_factory",
            side_effect=RuntimeError("DB gone"),
        ):
            result = await build_sentiment(state)

        section = result["sentiment_section"]
        assert section.content["available"] is False
        assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Node: build_sources
# ---------------------------------------------------------------------------


class TestBuildSources:
    """Tests for the build_sources node."""

    def test_sources_deduplicates(self):
        from alphawatch.agents.nodes.brief import build_sources

        chunks = [
            ChunkResult(
                chunk_id=f"c{i}",
                document_id="shared-doc",
                content=f"Content {i}",
                similarity=0.9,
                source_type="edgar_10k",
                source_url="https://example.com",
                title="10-K 2025",
            )
            for i in range(3)
        ]

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunks": chunks,
            "errors": [],
        }

        result = build_sources(state)
        section = result["sources_section"]
        assert section.section_type == "sources"
        assert section.section_order == 5
        assert section.content["total_chunks_retrieved"] == 3
        assert section.content["total_documents"] == 1

    def test_sources_empty_chunks(self):
        from alphawatch.agents.nodes.brief import build_sources

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunks": [],
            "errors": [],
        }

        result = build_sources(state)
        section = result["sources_section"]
        assert section.content["sources"] == []
        assert section.content["total_documents"] == 0


# ---------------------------------------------------------------------------
# Node: assemble_sections
# ---------------------------------------------------------------------------


class TestAssembleSections:
    """Tests for the assemble_sections fan-in node."""

    def test_assembles_all_sections_sorted(self):
        from alphawatch.agents.nodes.brief import assemble_sections

        snap = BriefSectionData("snapshot", 1, {"available": True})
        what = BriefSectionData(
            "what_changed", 2, {"has_changes": False, "changes": []}
        )
        risk = BriefSectionData("risk_flags", 3, {"flags": []})
        sent = BriefSectionData("sentiment", 4, {"available": False})
        srcs = BriefSectionData("sources", 5, {"sources": []})

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
            "snapshot_section": snap,
            "what_changed_section": what,
            "risk_flags_section": risk,
            "sentiment_section": sent,
            "sources_section": srcs,
        }

        result = assemble_sections(state)
        sections = result["sections"]
        assert len(sections) == 5
        orders = [s.section_order for s in sections]
        assert orders == sorted(orders)

    def test_missing_sections_skipped(self):
        from alphawatch.agents.nodes.brief import assemble_sections

        snap = BriefSectionData("snapshot", 1, {"available": True})

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
            "snapshot_section": snap,
            # other sections absent
        }

        result = assemble_sections(state)
        assert len(result["sections"]) == 1


# ---------------------------------------------------------------------------
# Node: build_executive_summary
# ---------------------------------------------------------------------------


class TestBuildExecutiveSummary:
    """Tests for the build_executive_summary node."""

    @pytest.mark.asyncio
    async def test_summary_generated(self):
        from alphawatch.agents.nodes.brief import build_executive_summary

        sections = [
            BriefSectionData(
                "snapshot",
                1,
                {
                    "available": True,
                    "snapshot_date": "2026-03-26",
                    "price": 182.5,
                    "market_cap": 2_800_000_000_000,
                    "pe_ratio": 28.4,
                    "debt_to_equity": 1.87,
                    "analyst_rating": "Strong Buy",
                },
            ),
            BriefSectionData(
                "what_changed",
                2,
                {
                    "has_changes": True,
                    "changes": [
                        {
                            "metric": "Price",
                            "previous": 170.0,
                            "current": 182.5,
                            "change_pct": 7.35,
                            "unit": "USD",
                            "from_date": "2026-03-19",
                            "to_date": "2026-03-26",
                        }
                    ],
                },
            ),
            BriefSectionData(
                "risk_flags",
                3,
                {
                    "flags": [
                        {
                            "severity": "medium",
                            "category": "regulatory",
                            "description": "FTC antitrust review ongoing.",
                        }
                    ]
                },
            ),
            BriefSectionData(
                "sentiment",
                4,
                {"available": True, "overall_label": "positive", "overall_score": 42.0},
            ),
        ]

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="d1",
                content="Apple revenue grew 12% YoY.",
                similarity=0.91,
                source_type="edgar_10k",
                source_url="",
                title="10-K",
            )
        ]

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={
                "summary": "Apple Inc. delivered strong performance with revenue up 12%.",
                "key_points": ["Revenue grew 12% YoY.", "FTC antitrust risk persists."],
                "source_chunk_ids": ["c1"],
            }
        )

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "sections": sections,
            "retrieved_chunks": chunks,
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.BedrockClient", return_value=mock_client
        ):
            result = await build_executive_summary(state)

        section = result["executive_summary_section"]
        assert section.section_type == "executive_summary"
        assert section.section_order == 6
        assert "Apple" in section.content["summary"]
        assert len(section.content["key_points"]) == 2
        assert "c1" in section.content["cited_chunk_ids"]

    @pytest.mark.asyncio
    async def test_summary_error_returns_fallback(self):
        from alphawatch.agents.nodes.brief import build_executive_summary

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(side_effect=RuntimeError("Timeout"))

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "sections": [],
            "retrieved_chunks": [],
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.BedrockClient", return_value=mock_client
        ):
            result = await build_executive_summary(state)

        section = result["executive_summary_section"]
        assert "unavailable" in section.content["summary"].lower()
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_cited_chunk_ids_filtered_to_known(self):
        """LLM cannot hallucinate chunk IDs that were not retrieved."""
        from alphawatch.agents.nodes.brief import build_executive_summary

        chunks = [
            ChunkResult(
                chunk_id="real-chunk-id",
                document_id="d1",
                content="Real content.",
                similarity=0.9,
                source_type="edgar_10k",
                source_url="",
                title="10-K",
            )
        ]

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={
                "summary": "Summary text.",
                "key_points": [],
                "source_chunk_ids": ["real-chunk-id", "hallucinated-id"],
            }
        )

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "sections": [],
            "retrieved_chunks": chunks,
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.BedrockClient", return_value=mock_client
        ):
            result = await build_executive_summary(state)

        cited = result["executive_summary_section"].content["cited_chunk_ids"]
        assert "real-chunk-id" in cited
        assert "hallucinated-id" not in cited


# ---------------------------------------------------------------------------
# Node: build_suggested_followups
# ---------------------------------------------------------------------------


class TestBuildSuggestedFollowups:
    """Tests for the build_suggested_followups node."""

    @pytest.mark.asyncio
    async def test_returns_questions(self):
        from alphawatch.agents.nodes.brief import build_suggested_followups

        exec_section = BriefSectionData(
            "executive_summary",
            6,
            {"summary": "Apple delivered strong revenue growth."},
        )
        risk_section = BriefSectionData(
            "risk_flags",
            3,
            {"flags": [{"severity": "high", "description": "FTC scrutiny."}]},
        )

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={
                "questions": [
                    "What drove revenue growth in this quarter?",
                    "How is Apple managing the FTC antitrust risk?",
                    "What is the outlook for Services segment margins?",
                    "How does Apple's debt-to-equity compare to peers?",
                ]
            }
        )

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "executive_summary_section": exec_section,
            "risk_flags_section": risk_section,
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.BedrockClient", return_value=mock_client
        ):
            result = await build_suggested_followups(state)

        section = result["suggested_followups_section"]
        assert section.section_type == "suggested_followups"
        assert section.section_order == 7
        assert len(section.content["questions"]) == 4

    @pytest.mark.asyncio
    async def test_error_returns_empty_questions(self):
        from alphawatch.agents.nodes.brief import build_suggested_followups

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(side_effect=RuntimeError("Haiku down"))

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.BedrockClient", return_value=mock_client
        ):
            result = await build_suggested_followups(state)

        section = result["suggested_followups_section"]
        assert section.content["questions"] == []
        assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Node: store_brief
# ---------------------------------------------------------------------------


class TestStoreBrief:
    """Tests for the store_brief node."""

    @pytest.mark.asyncio
    async def test_stores_brief_and_returns_id(self):
        from alphawatch.agents.nodes.brief import store_brief

        brief_id = uuid.uuid4()
        mock_brief = Mock()
        mock_brief.id = brief_id

        mock_repo = AsyncMock()
        mock_repo.create_brief = AsyncMock(return_value=mock_brief)
        mock_repo.bulk_create_sections = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        sections = [
            BriefSectionData("snapshot", 1, {"available": True}),
            BriefSectionData("executive_summary", 6, {"summary": "Test."}),
        ]

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_id": str(uuid.uuid4()),
            "sections": [sections[0]],
            "executive_summary_section": sections[1],
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.BriefRepository", return_value=mock_repo
            ),
        ):
            result = await store_brief(state)

        assert result["brief_id"] == str(brief_id)
        assert result["errors"] == []
        mock_repo.create_brief.assert_called_once()
        mock_repo.bulk_create_sections.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_error_returns_empty_id(self):
        from alphawatch.agents.nodes.brief import store_brief

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
            "sections": [],
        }

        with patch(
            "alphawatch.agents.nodes.brief.async_session_factory",
            side_effect=RuntimeError("DB unreachable"),
        ):
            result = await store_brief(state)

        assert result["brief_id"] == ""
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_fallback_user_id_when_absent(self):
        from alphawatch.agents.nodes.brief import store_brief

        brief_id = uuid.uuid4()
        mock_brief = Mock()
        mock_brief.id = brief_id
        mock_repo = AsyncMock()
        mock_repo.create_brief = AsyncMock(return_value=mock_brief)
        mock_repo.bulk_create_sections = AsyncMock(return_value=[])
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        state: BriefState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            # user_id intentionally absent
            "sections": [],
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.brief.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.brief.BriefRepository", return_value=mock_repo
            ),
        ):
            result = await store_brief(state)

        assert result["brief_id"] == str(brief_id)
        # user_id should have fallen back to uuid(int=0) — call should still succeed
        _, kwargs = mock_repo.create_brief.call_args
        assert kwargs["user_id"] == uuid.UUID(int=0)


# ---------------------------------------------------------------------------
# Node: handle_errors
# ---------------------------------------------------------------------------


class TestHandleErrors:
    """Tests for the handle_errors terminal node."""

    def test_logs_errors(self, caplog):
        from alphawatch.agents.nodes.brief import handle_errors

        state: BriefState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "errors": [
                "retrieve_chunks failed: timeout",
                "store_brief failed: db error",
            ],
            "brief_id": "",
        }

        import logging

        with caplog.at_level(logging.ERROR, logger="alphawatch.agents.nodes.brief"):
            result = handle_errors(state)

        assert result == {}
        assert len(caplog.records) == 2

    def test_no_errors_logs_success(self, caplog):
        from alphawatch.agents.nodes.brief import handle_errors

        state: BriefState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "errors": [],
            "brief_id": "brief-uuid-here",
        }

        import logging

        with caplog.at_level(logging.INFO, logger="alphawatch.agents.nodes.brief"):
            result = handle_errors(state)

        assert result == {}
        assert any("successfully" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# BriefGraph compilation
# ---------------------------------------------------------------------------


class TestBriefGraph:
    """Tests for BriefGraph compilation and structure."""

    def test_graph_compiles(self):
        from alphawatch.agents.graphs.brief import build_brief_graph

        graph = build_brief_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self):
        from alphawatch.agents.graphs.brief import build_brief_graph

        graph = build_brief_graph()
        node_names = set(graph.get_graph().nodes.keys())

        expected = {
            "retrieve_chunks",
            "build_snapshot",
            "build_what_changed",
            "build_risk_flags",
            "build_sentiment",
            "build_sources",
            "assemble_sections",
            "build_executive_summary",
            "build_suggested_followups",
            "store_brief",
            "handle_errors",
        }
        for node in expected:
            assert node in node_names, f"Missing node: {node}"

    def test_graph_has_correct_edge_count(self):
        from alphawatch.agents.graphs.brief import build_brief_graph

        graph = build_brief_graph()
        edges = graph.get_graph().edges
        # 5 fan-in edges (section builders → assemble_sections)
        # + 5 sequential tail edges
        # + conditional fan-out from retrieve_chunks
        assert len(edges) >= 10


# ---------------------------------------------------------------------------
# BriefRepository
# ---------------------------------------------------------------------------


class TestBriefRepository:
    """Tests for BriefRepository — schema, logic, and validation."""

    @pytest.mark.asyncio
    async def test_create_brief(self):
        from alphawatch.repositories.briefs import BriefRepository

        brief_id = uuid.uuid4()
        mock_brief = Mock()
        mock_brief.id = brief_id

        mock_session = AsyncMock()
        mock_session.add = Mock()
        mock_session.flush = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_brief)

        repo = BriefRepository(mock_session)

        user_id = uuid.uuid4()
        company_id = uuid.uuid4()
        session_id = uuid.uuid4()

        # Patch the flush to set the ID on the created object
        created_briefs: list[Any] = []

        def capture_add(obj: Any) -> None:
            obj.id = brief_id
            created_briefs.append(obj)

        mock_session.add.side_effect = capture_add

        brief = await repo.create_brief(user_id, company_id, session_id)
        assert brief.id == brief_id

    @pytest.mark.asyncio
    async def test_bulk_create_sections(self):
        from alphawatch.repositories.briefs import BriefRepository

        mock_session = AsyncMock()
        mock_session.add_all = Mock()
        mock_session.flush = AsyncMock()

        repo = BriefRepository(mock_session)

        brief_id = uuid.uuid4()
        sections = [
            BriefSectionData("snapshot", 1, {"price": 182.5}),
            BriefSectionData("what_changed", 2, {"has_changes": False, "changes": []}),
            BriefSectionData("executive_summary", 6, {"summary": "Test summary."}),
        ]

        result = await repo.bulk_create_sections(brief_id, sections)
        mock_session.add_all.assert_called_once()
        call_args = mock_session.add_all.call_args[0][0]
        assert len(call_args) == 3
        assert call_args[0].section_type == "snapshot"
        assert call_args[2].section_type == "executive_summary"

    def test_section_order_preserved(self):
        from alphawatch.models.brief import BriefSection
        from alphawatch.repositories.briefs import BriefRepository

        # Verify BriefSection model attributes
        section = BriefSection(
            brief_id=uuid.uuid4(),
            section_type="snapshot",
            section_order=1,
            content={"price": 182.5},
        )
        assert section.section_type == "snapshot"
        assert section.section_order == 1


# ---------------------------------------------------------------------------
# ChunkRepository
# ---------------------------------------------------------------------------


class TestChunkRepository:
    """Tests for ChunkRepository."""

    @pytest.mark.asyncio
    async def test_get_chunks_by_ids_empty(self):
        from alphawatch.repositories.chunks import ChunkRepository

        mock_session = AsyncMock()
        repo = ChunkRepository(mock_session)

        result = await repo.get_chunks_by_ids([])
        assert result == []
        # Should not hit the database for empty input
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_similarity_search_parameters(self):
        from alphawatch.repositories.chunks import ChunkRepository

        mock_result = AsyncMock()
        mock_result.mappings = Mock(return_value=Mock(all=Mock(return_value=[])))
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = ChunkRepository(mock_session)
        company_id = uuid.uuid4()
        embedding = [0.1] * 1536

        results = await repo.similarity_search(
            company_id=company_id,
            query_embedding=embedding,
            top_k=5,
        )

        assert results == []
        mock_session.execute.assert_called_once()
        call_kwargs = mock_session.execute.call_args[0][1]
        assert call_kwargs["top_k"] == 5
        assert call_kwargs["company_id"] == str(company_id)


# ---------------------------------------------------------------------------
# Integration / exports
# ---------------------------------------------------------------------------


class TestBriefIntegration:
    """Integration tests: state in agents module, graph exported."""

    def test_brief_state_in_agents_module(self):
        from alphawatch.agents.state import (
            BriefSectionData,
            BriefState,
            ChunkResult,
            RiskFlagItem,
        )

        assert BriefState is not None
        assert ChunkResult is not None
        assert BriefSectionData is not None
        assert RiskFlagItem is not None

    def test_brief_graph_builder_exported(self):
        from alphawatch.agents.graphs import build_brief_graph

        assert callable(build_brief_graph)

    def test_brief_repository_exported(self):
        from alphawatch.repositories import BriefRepository

        assert BriefRepository is not None

    def test_chunk_repository_exported(self):
        from alphawatch.repositories import ChunkRepository

        assert ChunkRepository is not None

    def test_financial_snapshot_repo_exported(self):
        from alphawatch.repositories import FinancialSnapshotRepository

        assert FinancialSnapshotRepository is not None

    def test_all_nodes_importable(self):
        from alphawatch.agents.nodes.brief import (
            assemble_sections,
            build_executive_summary,
            build_risk_flags,
            build_sentiment,
            build_snapshot,
            build_sources,
            build_suggested_followups,
            build_what_changed,
            handle_errors,
            retrieve_chunks,
            store_brief,
        )

        for fn in (
            assemble_sections,
            build_executive_summary,
            build_risk_flags,
            build_sentiment,
            build_snapshot,
            build_sources,
            build_suggested_followups,
            build_what_changed,
            handle_errors,
            retrieve_chunks,
            store_brief,
        ):
            assert callable(fn)

    def test_section_order_constants(self):
        from alphawatch.agents.nodes.brief import (
            ORDER_EXECUTIVE_SUMMARY,
            ORDER_RISK_FLAGS,
            ORDER_SENTIMENT,
            ORDER_SNAPSHOT,
            ORDER_SOURCES,
            ORDER_SUGGESTED_FOLLOWUPS,
            ORDER_WHAT_CHANGED,
        )

        orders = [
            ORDER_SNAPSHOT,
            ORDER_WHAT_CHANGED,
            ORDER_RISK_FLAGS,
            ORDER_SENTIMENT,
            ORDER_SOURCES,
            ORDER_EXECUTIVE_SUMMARY,
            ORDER_SUGGESTED_FOLLOWUPS,
        ]
        # All orders must be unique and sequential
        assert len(set(orders)) == 7
        assert orders == sorted(orders)
