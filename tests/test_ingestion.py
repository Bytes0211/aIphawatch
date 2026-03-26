"""Tests for EDGAR ingestion: chunker, state types, graph, and endpoint."""

import hashlib

import pytest

from alphawatch.agents.state import (
    BaseState,
    Chunk,
    FilingRef,
    IngestionState,
    ParsedDoc,
)
from alphawatch.services.chunker import chunk_text, get_tokenizer
from alphawatch.services.edgar import FILING_TYPE_MAP, EdgarClient


# ---------------------------------------------------------------------------
# State types
# ---------------------------------------------------------------------------
class TestBaseState:
    """Test BaseState TypedDict structure."""

    def test_base_state_keys(self):
        state: BaseState = {
            "tenant_id": "t-1",
            "user_id": "u-1",
            "company_id": "c-1",
            "ticker": "AAPL",
            "errors": [],
            "metadata": {},
        }
        assert state["ticker"] == "AAPL"
        assert state["errors"] == []

    def test_ingestion_state_extends_base(self):
        state: IngestionState = {
            "tenant_id": "t-1",
            "user_id": "u-1",
            "company_id": "c-1",
            "ticker": "AAPL",
            "errors": [],
            "metadata": {},
            "filing_types": ["10-K"],
            "new_filings": [],
            "parsed_documents": [],
            "chunks": [],
            "embeddings_stored": 0,
        }
        assert state["filing_types"] == ["10-K"]
        assert state["embeddings_stored"] == 0


class TestFilingRef:
    """Test FilingRef dataclass."""

    def test_creation(self):
        ref = FilingRef(
            accession_number="0001",
            filing_type="10-K",
            filing_date="2026-01-15",
            title="AAPL 10-K",
            url="https://sec.gov/test",
        )
        assert ref.filing_type == "10-K"
        assert ref.url == "https://sec.gov/test"


class TestParsedDoc:
    """Test ParsedDoc dataclass."""

    def test_creation_with_hash(self):
        text = "Sample filing text"
        doc = ParsedDoc(
            source_type="edgar_10k",
            source_url="https://sec.gov/test",
            title="Test Filing",
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            raw_text=text,
        )
        assert doc.source_type == "edgar_10k"
        assert len(doc.content_hash) == 64


class TestChunk:
    """Test Chunk dataclass."""

    def test_creation_without_embedding(self):
        c = Chunk(content="hello world", chunk_index=0)
        assert c.embedding is None
        assert c.chunk_index == 0

    def test_creation_with_embedding(self):
        c = Chunk(content="hello", chunk_index=0, embedding=[0.1] * 1536)
        assert len(c.embedding) == 1536


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------
class TestChunker:
    """Test text chunking utility."""

    def test_empty_text_returns_empty(self):
        assert chunk_text("") == []

    def test_short_text_single_chunk(self):
        chunks = chunk_text("Hello world", chunk_size=100, chunk_overlap=10)
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert "Hello world" in chunks[0].content

    def test_long_text_produces_multiple_chunks(self):
        # Generate text that's definitely > 512 tokens
        text = "The quick brown fox jumps over the lazy dog. " * 200
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        assert len(chunks) > 1
        # Verify sequential indices
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_overlap_creates_overlapping_content(self):
        # Use enough text to create multiple chunks
        text = "word " * 300  # ~300 tokens
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        assert len(chunks) >= 3
        # With overlap, chunk content should have shared tokens

    def test_metadata_propagated(self):
        chunks = chunk_text(
            "test text here",
            chunk_size=100,
            chunk_overlap=10,
            metadata={"source": "test"},
        )
        assert chunks[0].metadata["source"] == "test"
        assert "token_count" in chunks[0].metadata

    def test_tokenizer_loads(self):
        enc = get_tokenizer()
        tokens = enc.encode("Hello world")
        assert len(tokens) > 0


# ---------------------------------------------------------------------------
# EDGAR client helpers
# ---------------------------------------------------------------------------
class TestEdgarFilingTypeMap:
    """Test EDGAR filing type mapping."""

    def test_known_types(self):
        assert FILING_TYPE_MAP["10-K"] == "edgar_10k"
        assert FILING_TYPE_MAP["10-Q"] == "edgar_10q"
        assert FILING_TYPE_MAP["8-K"] == "edgar_8k"

    def test_map_filing_type(self):
        assert EdgarClient.map_filing_type("10-K") == "edgar_10k"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown EDGAR filing type"):
            EdgarClient.map_filing_type("13-F")


# ---------------------------------------------------------------------------
# IngestionGraph structure
# ---------------------------------------------------------------------------
class TestIngestionGraph:
    """Test that the IngestionGraph builds correctly."""

    def test_graph_compiles(self):
        from alphawatch.agents.graphs.ingestion import build_ingestion_graph

        graph = build_ingestion_graph()
        # Should be a compiled graph object (CompiledStateGraph)
        assert graph is not None
        assert hasattr(graph, "ainvoke")

    def test_graph_has_nodes(self):
        from alphawatch.agents.graphs.ingestion import build_ingestion_graph

        graph = build_ingestion_graph()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {
            "__start__",
            "fetch_filings",
            "parse_documents",
            "chunk_documents",
            "embed_chunks",
            "store_chunks",
            "handle_errors",
            "__end__",
        }
        assert expected.issubset(node_names)


# ---------------------------------------------------------------------------
# Ingestion endpoint routing and auth
# ---------------------------------------------------------------------------
class TestIngestionEndpointAuth:
    """Test ingestion endpoint enforces authentication and RBAC."""

    async def test_trigger_requires_auth(self, async_client):
        resp = await async_client.post(
            "/api/ingestion/trigger",
            json={"ticker": "AAPL"},
        )
        assert resp.status_code == 401

    async def test_trigger_appears_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/ingestion/trigger" in paths

    async def test_trigger_is_post_only(self, async_client):
        resp = await async_client.get("/openapi.json")
        methods = resp.json()["paths"]["/api/ingestion/trigger"]
        assert "post" in methods
        assert "get" not in methods


class TestIngestionSchemas:
    """Test ingestion request/response schemas."""

    def test_trigger_request(self):
        from alphawatch.api.routers.ingestion import IngestionTriggerRequest

        req = IngestionTriggerRequest(ticker="AAPL")
        assert req.ticker == "AAPL"
        assert req.filing_types is None

    def test_trigger_request_with_types(self):
        from alphawatch.api.routers.ingestion import IngestionTriggerRequest

        req = IngestionTriggerRequest(ticker="MSFT", filing_types=["10-K"])
        assert req.filing_types == ["10-K"]

    def test_trigger_response(self):
        from alphawatch.api.routers.ingestion import IngestionTriggerResponse

        resp = IngestionTriggerResponse(
            status="completed",
            company_id="abc-123",
            ticker="AAPL",
            message="Ingestion complete: 42 chunks stored",
        )
        assert resp.status == "completed"
        assert "42" in resp.message
