"""Tests for ChatGraph: state types, node functions, graph, repository, schemas, and routing."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from alphawatch.agents.state import (
    ChatMessage,
    ChatState,
    ChunkResult,
    Citation,
)

# ---------------------------------------------------------------------------
# State type tests
# ---------------------------------------------------------------------------


class TestCitation:
    """Tests for Citation dataclass."""

    def test_creation_minimal(self):
        cit = Citation(
            chunk_id="c1",
            document_id="d1",
            title="Apple 10-K 2025",
            source_type="edgar_10k",
            source_url="https://example.com/filing",
        )
        assert cit.chunk_id == "c1"
        assert cit.excerpt == ""

    def test_creation_with_excerpt(self):
        cit = Citation(
            chunk_id="c2",
            document_id="d2",
            title="Apple 10-Q",
            source_type="edgar_10q",
            source_url="https://example.com/10q",
            excerpt="Revenue grew 12% year-over-year.",
        )
        assert cit.excerpt == "Revenue grew 12% year-over-year."


class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_user_message(self):
        msg = ChatMessage(role="user", content="What is Apple's revenue?")
        assert msg.role == "user"
        assert msg.citations == []
        assert msg.turn_index == 0
        assert msg.created_at == ""

    def test_assistant_message_with_citations(self):
        cit = Citation(
            chunk_id="c1",
            document_id="d1",
            title="Apple 10-K",
            source_type="edgar_10k",
            source_url="",
        )
        msg = ChatMessage(
            role="assistant",
            content="Apple's revenue was $394B.",
            citations=[cit],
            turn_index=1,
            created_at="2026-03-26T12:00:00+00:00",
        )
        assert msg.role == "assistant"
        assert len(msg.citations) == 1
        assert msg.turn_index == 1

    def test_system_message(self):
        msg = ChatMessage(role="system", content="[Earlier summary]")
        assert msg.role == "system"


class TestChatState:
    """Tests for ChatState TypedDict."""

    def test_minimal_state(self):
        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
        }
        assert state["ticker"] == "AAPL"

    def test_full_state(self):
        chunk = ChunkResult(
            chunk_id="ch1",
            document_id="d1",
            content="Revenue data.",
            similarity=0.9,
            source_type="edgar_10k",
            source_url="",
            title="10-K",
        )
        msg = ChatMessage(role="user", content="Hello")
        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "session_id": str(uuid.uuid4()),
            "user_message": "What changed this quarter?",
            "messages": [msg],
            "context_summary": "Earlier we discussed revenue.",
            "summary_through": 4,
            "retrieved_chunk_ids": ["ch1"],
            "retrieved_chunks": [chunk],
            "new_chunk_ids": ["ch1"],
            "cache_hit": False,
            "intent": "rag",
            "comparison_entity": "",
            "llm_context": [msg],
            "response": "Revenue grew 12%.",
            "citations": [],
            "suggested_followups": ["What drove growth?"],
            "errors": [],
        }
        assert state["company_name"] == "Apple Inc."
        assert state["intent"] == "rag"
        assert len(state["retrieved_chunks"]) == 1

    def test_optional_fields_absent(self):
        state: ChatState = {"company_id": "c-1", "ticker": "MSFT"}
        assert "session_id" not in state
        assert "messages" not in state
        assert "response" not in state


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestChatNodeHelpers:
    """Tests for private helper functions in chat nodes."""

    def test_format_messages_for_prompt(self):
        from alphawatch.agents.nodes.chat import _format_messages_for_prompt

        messages = [
            ChatMessage(role="user", content="What is AAPL revenue?"),
            ChatMessage(role="assistant", content="Revenue is $394B."),
        ]
        result = _format_messages_for_prompt(messages)
        assert "USER: What is AAPL revenue?" in result
        assert "ASSISTANT: Revenue is $394B." in result

    def test_format_messages_empty(self):
        from alphawatch.agents.nodes.chat import _format_messages_for_prompt

        assert _format_messages_for_prompt([]) == ""

    def test_format_chunks_for_prompt(self):
        from alphawatch.agents.nodes.chat import _format_chunks_for_prompt

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="d1",
                content="Apple had strong earnings.",
                similarity=0.95,
                source_type="edgar_10k",
                source_url="",
                title="10-K 2025",
            )
        ]
        result = _format_chunks_for_prompt(chunks)
        assert "[1]" in result
        assert "10-K 2025" in result
        assert "Apple had strong earnings." in result

    def test_format_chunks_respects_max_chars(self):
        from alphawatch.agents.nodes.chat import _format_chunks_for_prompt

        chunks = [
            ChunkResult(
                chunk_id=f"c{i}",
                document_id=f"d{i}",
                content="x" * 600,
                similarity=0.9 - i * 0.01,
                source_type="edgar_10k",
                source_url="",
                title=f"Doc {i}",
            )
            for i in range(5)
        ]
        result = _format_chunks_for_prompt(chunks, max_chars=700)
        # Only the first chunk should fit
        assert "Doc 1" not in result

    def test_build_citations_deduplicates_by_document(self):
        from alphawatch.agents.nodes.chat import _build_citations

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="shared-doc",
                content="First chunk.",
                similarity=0.95,
                source_type="edgar_10k",
                source_url="https://example.com",
                title="Shared Doc",
            ),
            ChunkResult(
                chunk_id="c2",
                document_id="shared-doc",
                content="Second chunk.",
                similarity=0.88,
                source_type="edgar_10k",
                source_url="https://example.com",
                title="Shared Doc",
            ),
            ChunkResult(
                chunk_id="c3",
                document_id="unique-doc",
                content="Different doc.",
                similarity=0.80,
                source_type="edgar_10q",
                source_url="https://other.com",
                title="Unique Doc",
            ),
        ]
        citations = _build_citations(chunks)
        assert len(citations) == 2
        doc_ids = {c.document_id for c in citations}
        assert "shared-doc" in doc_ids
        assert "unique-doc" in doc_ids

    def test_build_citations_excerpt_truncated(self):
        from alphawatch.agents.nodes.chat import _build_citations

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="d1",
                content="A" * 400,
                similarity=0.9,
                source_type="edgar_10k",
                source_url="",
                title="Doc",
            )
        ]
        citations = _build_citations(chunks)
        assert len(citations[0].excerpt) <= 200

    def test_build_citations_empty(self):
        from alphawatch.agents.nodes.chat import _build_citations

        assert _build_citations([]) == []

    def test_now_iso_returns_utc_string(self):
        from alphawatch.agents.nodes.chat import _now_iso

        result = _now_iso()
        assert "T" in result
        assert "+00:00" in result or "Z" in result or len(result) > 10


# ---------------------------------------------------------------------------
# Node: prepare_context
# ---------------------------------------------------------------------------


class TestPrepareContext:
    """Tests for the prepare_context node."""

    @pytest.mark.asyncio
    async def test_loads_session_and_builds_context(self):
        from alphawatch.agents.nodes.chat import prepare_context

        session_id = uuid.uuid4()
        mock_db_session = Mock()
        mock_db_session.messages = [
            {
                "role": "user",
                "content": "Hello",
                "citations": [],
                "turn_index": 0,
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ]
        mock_db_session.context_summary = None
        mock_db_session.context_summary_through = 0
        mock_db_session.retrieved_chunk_ids = []

        mock_repo = AsyncMock()
        mock_repo.get_session = AsyncMock(return_value=mock_db_session)

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "session_id": str(session_id),
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChatRepository",
                return_value=mock_repo,
            ),
        ):
            result = await prepare_context(state)

        assert len(result["messages"]) == 1
        assert result["messages"][0].role == "user"
        assert result["context_summary"] == ""
        assert result["retrieved_chunk_ids"] == []
        assert isinstance(result["llm_context"], list)

    @pytest.mark.asyncio
    async def test_prepends_summary_as_system_message(self):
        from alphawatch.agents.nodes.chat import prepare_context

        mock_db_session = Mock()
        mock_db_session.messages = []
        mock_db_session.context_summary = "Earlier we discussed revenue growth."
        mock_db_session.context_summary_through = 8
        mock_db_session.retrieved_chunk_ids = []

        mock_repo = AsyncMock()
        mock_repo.get_session = AsyncMock(return_value=mock_db_session)
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "session_id": str(uuid.uuid4()),
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChatRepository",
                return_value=mock_repo,
            ),
        ):
            result = await prepare_context(state)

        # The summary should appear as the first system message in llm_context
        assert len(result["llm_context"]) >= 1
        assert result["llm_context"][0].role == "system"
        assert "Earlier we discussed" in result["llm_context"][0].content

    @pytest.mark.asyncio
    async def test_missing_session_id_returns_empties(self):
        from alphawatch.agents.nodes.chat import prepare_context

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }

        result = await prepare_context(state)

        assert result["messages"] == []
        assert result["llm_context"] == []
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_session_not_found_returns_empties(self):
        from alphawatch.agents.nodes.chat import prepare_context

        mock_repo = AsyncMock()
        mock_repo.get_session = AsyncMock(return_value=None)
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "session_id": str(uuid.uuid4()),
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChatRepository",
                return_value=mock_repo,
            ),
        ):
            result = await prepare_context(state)

        assert result["messages"] == []
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_limits_llm_context_to_window(self):
        from alphawatch.agents.nodes.chat import RAW_MESSAGE_WINDOW, prepare_context

        # Create more messages than the window
        many_messages = [
            {
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}",
                "citations": [],
                "turn_index": i,
                "created_at": "",
            }
            for i in range(RAW_MESSAGE_WINDOW + 5)
        ]

        mock_db_session = Mock()
        mock_db_session.messages = many_messages
        mock_db_session.context_summary = None
        mock_db_session.context_summary_through = 0
        mock_db_session.retrieved_chunk_ids = []

        mock_repo = AsyncMock()
        mock_repo.get_session = AsyncMock(return_value=mock_db_session)
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "session_id": str(uuid.uuid4()),
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChatRepository",
                return_value=mock_repo,
            ),
        ):
            result = await prepare_context(state)

        # llm_context should not exceed RAW_MESSAGE_WINDOW
        assert len(result["llm_context"]) <= RAW_MESSAGE_WINDOW


# ---------------------------------------------------------------------------
# Node: detect_intent
# ---------------------------------------------------------------------------


class TestDetectIntent:
    """Tests for the detect_intent node."""

    @pytest.mark.asyncio
    async def test_classifies_rag_intent(self):
        from alphawatch.agents.nodes.chat import detect_intent

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={"intent": "rag", "comparison_ticker": ""}
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "What was Apple's revenue last quarter?",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await detect_intent(state)

        assert result["intent"] == "rag"
        assert result["comparison_entity"] == ""

    @pytest.mark.asyncio
    async def test_classifies_comparison_intent_with_ticker(self):
        from alphawatch.agents.nodes.chat import detect_intent

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={"intent": "comparison", "comparison_ticker": "MSFT"}
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "How does Apple compare to Microsoft on margins?",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await detect_intent(state)

        assert result["intent"] == "comparison"
        assert result["comparison_entity"] == "MSFT"

    @pytest.mark.asyncio
    async def test_classifies_general_intent(self):
        from alphawatch.agents.nodes.chat import detect_intent

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={"intent": "general", "comparison_ticker": ""}
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "Thanks, that's helpful.",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await detect_intent(state)

        assert result["intent"] == "general"

    @pytest.mark.asyncio
    async def test_invalid_intent_defaults_to_rag(self):
        from alphawatch.agents.nodes.chat import detect_intent

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={"intent": "unknown_value", "comparison_ticker": ""}
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "Some question.",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await detect_intent(state)

        assert result["intent"] == "rag"

    @pytest.mark.asyncio
    async def test_llm_error_falls_back_to_rag(self):
        from alphawatch.agents.nodes.chat import detect_intent

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            side_effect=RuntimeError("Bedrock unavailable")
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "What is revenue?",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await detect_intent(state)

        assert result["intent"] == "rag"
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_empty_message_returns_general(self):
        from alphawatch.agents.nodes.chat import detect_intent

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "",
            "errors": [],
        }

        result = await detect_intent(state)
        assert result["intent"] == "general"


# ---------------------------------------------------------------------------
# Node: check_chunk_cache
# ---------------------------------------------------------------------------


class TestCheckChunkCache:
    """Tests for the check_chunk_cache node."""

    @pytest.mark.asyncio
    async def test_cache_hit_loads_chunks(self):
        from alphawatch.agents.nodes.chat import check_chunk_cache

        chunk_id = uuid.uuid4()
        mock_db_chunk = Mock()
        mock_db_chunk.id = chunk_id
        mock_db_chunk.document_id = uuid.uuid4()
        mock_db_chunk.content = "Cached chunk content."
        mock_db_chunk.metadata_ = {
            "source_type": "edgar_10k",
            "source_url": "https://example.com",
            "title": "10-K 2025",
        }

        mock_repo = AsyncMock()
        mock_repo.get_chunks_by_ids = AsyncMock(return_value=[mock_db_chunk])
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunk_ids": [str(chunk_id)],
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChunkRepository",
                return_value=mock_repo,
            ),
        ):
            result = await check_chunk_cache(state)

        assert result["cache_hit"] is True
        assert len(result["retrieved_chunks"]) == 1
        assert result["retrieved_chunks"][0].chunk_id == str(chunk_id)

    @pytest.mark.asyncio
    async def test_empty_cache_returns_miss(self):
        from alphawatch.agents.nodes.chat import check_chunk_cache

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunk_ids": [],
            "errors": [],
        }

        result = await check_chunk_cache(state)

        assert result["cache_hit"] is False
        assert result["retrieved_chunks"] == []

    @pytest.mark.asyncio
    async def test_db_returns_empty_means_cache_miss(self):
        from alphawatch.agents.nodes.chat import check_chunk_cache

        mock_repo = AsyncMock()
        mock_repo.get_chunks_by_ids = AsyncMock(return_value=[])
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunk_ids": [str(uuid.uuid4())],
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChunkRepository",
                return_value=mock_repo,
            ),
        ):
            result = await check_chunk_cache(state)

        assert result["cache_hit"] is False

    @pytest.mark.asyncio
    async def test_error_returns_cache_miss(self):
        from alphawatch.agents.nodes.chat import check_chunk_cache

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "retrieved_chunk_ids": [str(uuid.uuid4())],
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.async_session_factory",
            side_effect=RuntimeError("DB down"),
        ):
            result = await check_chunk_cache(state)

        assert result["cache_hit"] is False
        assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Node: retrieve_chunks
# ---------------------------------------------------------------------------


class TestRetrieveChunks:
    """Tests for the retrieve_chunks node."""

    @pytest.mark.asyncio
    async def test_retrieves_and_merges_with_cache(self):
        from alphawatch.agents.nodes.chat import retrieve_chunks

        existing_chunk = ChunkResult(
            chunk_id="cached-id",
            document_id="d-old",
            content="Cached content.",
            similarity=1.0,
            source_type="edgar_10k",
            source_url="",
            title="Old Doc",
        )
        fresh_chunk = ChunkResult(
            chunk_id="fresh-id",
            document_id="d-new",
            content="New content.",
            similarity=0.92,
            source_type="edgar_10k",
            source_url="",
            title="New Doc",
        )

        mock_embed_svc = Mock()
        mock_embed_svc.embed_text = Mock(return_value=[0.1] * 1536)

        mock_repo = AsyncMock()
        mock_repo.similarity_search = AsyncMock(return_value=[fresh_chunk])

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "What is the revenue?",
            "retrieved_chunks": [existing_chunk],
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.EmbeddingsService",
                return_value=mock_embed_svc,
            ),
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChunkRepository",
                return_value=mock_repo,
            ),
        ):
            result = await retrieve_chunks(state)

        # Should include both the cached chunk and the fresh one
        assert len(result["retrieved_chunks"]) == 2
        chunk_ids = {c.chunk_id for c in result["retrieved_chunks"]}
        assert "cached-id" in chunk_ids
        assert "fresh-id" in chunk_ids
        assert result["new_chunk_ids"] == ["fresh-id"]

    @pytest.mark.asyncio
    async def test_deduplicates_already_cached_chunks(self):
        from alphawatch.agents.nodes.chat import retrieve_chunks

        existing_chunk = ChunkResult(
            chunk_id="already-cached",
            document_id="d1",
            content="Content.",
            similarity=1.0,
            source_type="edgar_10k",
            source_url="",
            title="Doc",
        )

        mock_embed_svc = Mock()
        mock_embed_svc.embed_text = Mock(return_value=[0.0] * 1536)

        # The similarity search returns the same chunk ID as cached
        mock_repo = AsyncMock()
        mock_repo.similarity_search = AsyncMock(return_value=[existing_chunk])
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "Question?",
            "retrieved_chunks": [existing_chunk],
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.EmbeddingsService",
                return_value=mock_embed_svc,
            ),
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChunkRepository",
                return_value=mock_repo,
            ),
        ):
            result = await retrieve_chunks(state)

        # Should still only have the one chunk (no duplicate)
        assert len(result["retrieved_chunks"]) == 1
        assert result["new_chunk_ids"] == []

    @pytest.mark.asyncio
    async def test_empty_message_returns_cached(self):
        from alphawatch.agents.nodes.chat import retrieve_chunks

        cached = ChunkResult(
            chunk_id="c1",
            document_id="d1",
            content="Content.",
            similarity=1.0,
            source_type="edgar_10k",
            source_url="",
            title="Doc",
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "",
            "retrieved_chunks": [cached],
            "errors": [],
        }

        result = await retrieve_chunks(state)

        assert result["retrieved_chunks"] == [cached]
        assert result["new_chunk_ids"] == []

    @pytest.mark.asyncio
    async def test_error_falls_back_to_cached(self):
        from alphawatch.agents.nodes.chat import retrieve_chunks

        cached = ChunkResult(
            chunk_id="c1",
            document_id="d1",
            content="Content.",
            similarity=1.0,
            source_type="edgar_10k",
            source_url="",
            title="Doc",
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "Question?",
            "retrieved_chunks": [cached],
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.EmbeddingsService",
            side_effect=RuntimeError("Embeddings unavailable"),
        ):
            result = await retrieve_chunks(state)

        assert result["retrieved_chunks"] == [cached]
        assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Node: generate_response
# ---------------------------------------------------------------------------


class TestGenerateResponse:
    """Tests for the generate_response node."""

    @pytest.mark.asyncio
    async def test_generates_response_with_citations(self):
        from alphawatch.agents.nodes.chat import generate_response

        chunks = [
            ChunkResult(
                chunk_id="c1",
                document_id="d1",
                content="Apple revenue was $394B in FY2025.",
                similarity=0.92,
                source_type="edgar_10k",
                source_url="https://example.com",
                title="Apple 10-K 2025",
            )
        ]

        mock_client = Mock()
        mock_client.invoke = Mock(
            return_value="Apple's revenue was $394B in FY2025 [1]."
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "user_message": "What was Apple's revenue?",
            "llm_context": [],
            "retrieved_chunks": chunks,
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await generate_response(state)

        assert "394B" in result["response"]
        assert len(result["citations"]) == 1
        assert result["citations"][0].title == "Apple 10-K 2025"

    @pytest.mark.asyncio
    async def test_generates_with_no_chunks(self):
        from alphawatch.agents.nodes.chat import generate_response

        mock_client = Mock()
        mock_client.invoke = Mock(return_value="I don't have source data for that.")

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "What is your favorite color?",
            "llm_context": [],
            "retrieved_chunks": [],
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await generate_response(state)

        assert result["response"] != ""
        assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_error_returns_fallback_message(self):
        from alphawatch.agents.nodes.chat import generate_response

        mock_client = Mock()
        mock_client.invoke = Mock(side_effect=RuntimeError("Bedrock timeout"))

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "user_message": "Question?",
            "llm_context": [],
            "retrieved_chunks": [],
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await generate_response(state)

        assert "unable to generate" in result["response"].lower()
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_includes_conversation_context(self):
        from alphawatch.agents.nodes.chat import generate_response

        captured_prompts: list[str] = []
        mock_client = Mock()

        def capture_invoke(prompt: str, **kwargs: Any) -> str:
            captured_prompts.append(prompt)
            return "Response text."

        mock_client.invoke = capture_invoke

        llm_context = [
            ChatMessage(role="user", content="Tell me about revenue."),
            ChatMessage(role="assistant", content="Revenue was $394B."),
        ]

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "And margins?",
            "llm_context": llm_context,
            "retrieved_chunks": [],
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            await generate_response(state)

        assert len(captured_prompts) == 1
        assert "Tell me about revenue." in captured_prompts[0]


# ---------------------------------------------------------------------------
# Node: generate_followups
# ---------------------------------------------------------------------------


class TestGenerateFollowups:
    """Tests for the generate_followups node."""

    @pytest.mark.asyncio
    async def test_returns_questions(self):
        from alphawatch.agents.nodes.chat import generate_followups

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={
                "questions": [
                    "What drove the revenue growth?",
                    "How do margins compare YoY?",
                    "What is the capex outlook?",
                ]
            }
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "What was revenue?",
            "response": "Revenue was $394B.",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await generate_followups(state)

        assert len(result["suggested_followups"]) == 3

    @pytest.mark.asyncio
    async def test_empty_response_returns_no_questions(self):
        from alphawatch.agents.nodes.chat import generate_followups

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "",
            "response": "",
            "errors": [],
        }

        result = await generate_followups(state)
        assert result["suggested_followups"] == []

    @pytest.mark.asyncio
    async def test_llm_error_returns_empty_list(self):
        from alphawatch.agents.nodes.chat import generate_followups

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(side_effect=RuntimeError("Haiku down"))

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "Question?",
            "response": "Some answer.",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await generate_followups(state)

        assert result["suggested_followups"] == []
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_caps_at_three_questions(self):
        from alphawatch.agents.nodes.chat import generate_followups

        mock_client = Mock()
        mock_client.invoke_with_json = Mock(
            return_value={"questions": [f"Question {i}?" for i in range(10)]}
        )

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "Question?",
            "response": "Answer.",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.BedrockClient", return_value=mock_client
        ):
            result = await generate_followups(state)

        assert len(result["suggested_followups"]) <= 3


# ---------------------------------------------------------------------------
# Node: persist_turn
# ---------------------------------------------------------------------------


class TestPersistTurn:
    """Tests for the persist_turn node."""

    @pytest.mark.asyncio
    async def test_appends_messages_and_updates_cache(self):
        from alphawatch.agents.nodes.chat import persist_turn

        session_id = uuid.uuid4()
        mock_session = Mock()

        mock_repo = AsyncMock()
        mock_repo.append_messages = AsyncMock(return_value=mock_session)
        mock_repo.update_chunk_cache = AsyncMock(return_value=mock_session)

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.commit = AsyncMock()

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "session_id": str(session_id),
            "user_message": "What is revenue?",
            "response": "Revenue was $394B.",
            "citations": [],
            "suggested_followups": ["What drove growth?"],
            "new_chunk_ids": ["chunk-uuid-1"],
            "messages": [],
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChatRepository",
                return_value=mock_repo,
            ),
        ):
            result = await persist_turn(state)

        mock_repo.append_messages.assert_called_once()
        mock_repo.update_chunk_cache.assert_called_once_with(
            session_id, ["chunk-uuid-1"]
        )
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_skips_cache_update_when_no_new_chunks(self):
        from alphawatch.agents.nodes.chat import persist_turn

        session_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.append_messages = AsyncMock(return_value=Mock())
        mock_repo.update_chunk_cache = AsyncMock()

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.commit = AsyncMock()

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "session_id": str(session_id),
            "user_message": "Hi",
            "response": "Hello.",
            "citations": [],
            "suggested_followups": [],
            "new_chunk_ids": [],  # empty — no cache update needed
            "messages": [],
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChatRepository",
                return_value=mock_repo,
            ),
        ):
            await persist_turn(state)

        mock_repo.update_chunk_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_session_id_appends_error(self):
        from alphawatch.agents.nodes.chat import persist_turn

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "user_message": "Hi",
            "response": "Hello.",
            "citations": [],
            "suggested_followups": [],
            "new_chunk_ids": [],
            "messages": [],
            "errors": [],
        }

        result = await persist_turn(state)
        assert len(result["errors"]) == 1
        assert "session_id missing" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_db_error_appends_error(self):
        from alphawatch.agents.nodes.chat import persist_turn

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "session_id": str(uuid.uuid4()),
            "user_message": "Hi",
            "response": "Hello.",
            "citations": [],
            "suggested_followups": [],
            "new_chunk_ids": [],
            "messages": [],
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.async_session_factory",
            side_effect=RuntimeError("DB gone"),
        ):
            result = await persist_turn(state)

        assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Node: maybe_summarize
# ---------------------------------------------------------------------------


class TestMaybeSummarize:
    """Tests for the maybe_summarize node."""

    @pytest.mark.asyncio
    async def test_does_not_summarize_below_threshold(self):
        from alphawatch.agents.nodes.chat import SUMMARY_THRESHOLD, maybe_summarize

        # Create fewer messages than the threshold requires
        messages = [
            ChatMessage(role="user", content=f"msg {i}")
            for i in range(SUMMARY_THRESHOLD - 5)
        ]

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "session_id": str(uuid.uuid4()),
            "messages": messages,
            "context_summary": "",
            "summary_through": 0,
            "errors": [],
        }

        result = await maybe_summarize(state)
        assert "context_summary" not in result or result.get("errors") == []

    @pytest.mark.asyncio
    async def test_summarizes_when_above_threshold(self):
        from alphawatch.agents.nodes.chat import (
            RAW_MESSAGE_WINDOW,
            SUMMARY_THRESHOLD,
            maybe_summarize,
        )

        # Create enough messages to trigger summarisation
        messages = [
            ChatMessage(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            for i in range(SUMMARY_THRESHOLD + 2)
        ]

        mock_client = Mock()
        mock_client.invoke = Mock(return_value="Summary of the earlier conversation.")

        mock_repo = AsyncMock()
        mock_repo.update_context_summary = AsyncMock(return_value=Mock())
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.commit = AsyncMock()

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "session_id": str(uuid.uuid4()),
            "messages": messages,
            "context_summary": "",
            "summary_through": 0,
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.BedrockClient",
                return_value=mock_client,
            ),
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_db,
            ),
            patch(
                "alphawatch.agents.nodes.chat.ChatRepository",
                return_value=mock_repo,
            ),
        ):
            result = await maybe_summarize(state)

        assert result.get("context_summary") == "Summary of the earlier conversation."
        mock_repo.update_context_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_nothing_new_to_summarize(self):
        from alphawatch.agents.nodes.chat import (
            RAW_MESSAGE_WINDOW,
            SUMMARY_THRESHOLD,
            maybe_summarize,
        )

        messages = [
            ChatMessage(role="user", content=f"msg {i}")
            for i in range(SUMMARY_THRESHOLD + 2)
        ]
        # summary_through already covers all except the raw window
        summarise_up_to = max(0, len(messages) - RAW_MESSAGE_WINDOW)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "session_id": str(uuid.uuid4()),
            "messages": messages,
            "context_summary": "Existing summary.",
            "summary_through": summarise_up_to,  # already summarised
            "errors": [],
        }

        result = await maybe_summarize(state)
        # Nothing new to do → returns early with no changes
        assert "context_summary" not in result or result.get("errors") == []


# ---------------------------------------------------------------------------
# Node: handle_errors
# ---------------------------------------------------------------------------


class TestHandleErrors:
    """Tests for the handle_errors terminal node."""

    def test_logs_errors(self, caplog):
        import logging

        from alphawatch.agents.nodes.chat import handle_errors

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "session_id": "s-1",
            "errors": ["retrieve_chunks failed", "persist_turn failed"],
        }

        with caplog.at_level(logging.ERROR, logger="alphawatch.agents.nodes.chat"):
            result = handle_errors(state)

        assert result == {}
        assert len(caplog.records) == 2

    def test_success_logs_info(self, caplog):
        import logging

        from alphawatch.agents.nodes.chat import handle_errors

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "session_id": "s-1",
            "errors": [],
        }

        with caplog.at_level(logging.INFO, logger="alphawatch.agents.nodes.chat"):
            result = handle_errors(state)

        assert result == {}
        assert any("successfully" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# ChatGraph routing
# ---------------------------------------------------------------------------


class TestChatGraphRouting:
    """Tests for the conditional routing functions in ChatGraph."""

    def test_route_by_intent_rag_goes_to_cache(self):
        from alphawatch.agents.graphs.chat import _route_by_intent

        state: ChatState = {"company_id": "c-1", "ticker": "AAPL", "intent": "rag"}
        assert _route_by_intent(state) == "check_chunk_cache"

    def test_route_by_intent_comparison_goes_to_cache(self):
        from alphawatch.agents.graphs.chat import _route_by_intent

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "intent": "comparison",
        }
        assert _route_by_intent(state) == "check_chunk_cache"

    def test_route_by_intent_general_skips_to_response(self):
        from alphawatch.agents.graphs.chat import _route_by_intent

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "intent": "general",
        }
        assert _route_by_intent(state) == "generate_response"

    def test_route_by_intent_missing_defaults_to_cache(self):
        from alphawatch.agents.graphs.chat import _route_by_intent

        state: ChatState = {"company_id": "c-1", "ticker": "AAPL"}
        assert _route_by_intent(state) == "check_chunk_cache"

    def test_route_by_cache_hit_skips_retrieval(self):
        from alphawatch.agents.graphs.chat import _route_by_cache

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "cache_hit": True,
        }
        assert _route_by_cache(state) == "generate_response"

    def test_route_by_cache_miss_triggers_retrieval(self):
        from alphawatch.agents.graphs.chat import _route_by_cache

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "cache_hit": False,
        }
        assert _route_by_cache(state) == "retrieve_chunks"

    def test_route_by_cache_missing_flag_triggers_retrieval(self):
        from alphawatch.agents.graphs.chat import _route_by_cache

        state: ChatState = {"company_id": "c-1", "ticker": "AAPL"}
        assert _route_by_cache(state) == "retrieve_chunks"


# ---------------------------------------------------------------------------
# ChatGraph compilation
# ---------------------------------------------------------------------------


class TestChatGraph:
    """Tests for ChatGraph compilation and structure."""

    def test_graph_compiles(self):
        from alphawatch.agents.graphs.chat import build_chat_graph

        graph = build_chat_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self):
        from alphawatch.agents.graphs.chat import build_chat_graph

        graph = build_chat_graph()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {
            "prepare_context",
            "detect_intent",
            "check_chunk_cache",
            "retrieve_chunks",
            "generate_response",
            "generate_followups",
            "persist_turn",
            "maybe_summarize",
            "handle_errors",
        }
        for node in expected:
            assert node in node_names, f"Missing node: {node}"

    def test_graph_has_conditional_edges(self):
        from alphawatch.agents.graphs.chat import build_chat_graph

        graph = build_chat_graph()
        edges = graph.get_graph().edges
        # Minimum: prepare→detect, detect→(2 branches), cache→(2 branches),
        # retrieve→generate, generate→followups, followups→persist,
        # persist→summarize, summarize→errors, errors→END = 10+
        assert len(edges) >= 10


# ---------------------------------------------------------------------------
# ChatRepository
# ---------------------------------------------------------------------------


class TestChatRepository:
    """Tests for ChatRepository methods."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        from alphawatch.repositories.chat import ChatRepository

        session_id = uuid.uuid4()
        created_sessions: list[Any] = []

        mock_db = AsyncMock()

        def capture_add(obj: Any) -> None:
            obj.id = session_id
            created_sessions.append(obj)

        mock_db.add = Mock(side_effect=capture_add)
        mock_db.flush = AsyncMock()

        repo = ChatRepository(mock_db)
        session = await repo.create_session(
            user_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            ticker="AAPL",
        )

        assert session.id == session_id
        assert session.active_company_ticker == "AAPL"
        assert session.messages == []
        assert session.retrieved_chunk_ids == []

    @pytest.mark.asyncio
    async def test_append_messages(self):
        from alphawatch.models.chat import ChatSession
        from alphawatch.repositories.chat import ChatRepository

        session_id = uuid.uuid4()
        mock_session = ChatSession(
            user_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            active_company_ticker="AAPL",
        )
        mock_session.id = session_id
        mock_session.messages = []

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_session)
        mock_db.flush = AsyncMock()

        repo = ChatRepository(mock_db)
        updated = await repo.append_messages(
            session_id=session_id,
            user_message={"role": "user", "content": "Hello"},
            assistant_message={"role": "assistant", "content": "Hi there"},
        )

        assert len(updated.messages) == 2
        assert updated.messages[0]["role"] == "user"
        assert updated.messages[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_append_messages_raises_for_missing_session(self):
        from alphawatch.repositories.chat import ChatRepository

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)

        repo = ChatRepository(mock_db)

        with pytest.raises(ValueError, match="not found"):
            await repo.append_messages(
                session_id=uuid.uuid4(),
                user_message={"role": "user", "content": "Hello"},
                assistant_message={"role": "assistant", "content": "Hi"},
            )

    @pytest.mark.asyncio
    async def test_update_chunk_cache_deduplicates(self):
        from alphawatch.models.chat import ChatSession
        from alphawatch.repositories.chat import ChatRepository

        existing_id = uuid.uuid4()
        session_id = uuid.uuid4()
        mock_session = ChatSession(
            user_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            active_company_ticker="AAPL",
        )
        mock_session.id = session_id
        mock_session.retrieved_chunk_ids = [existing_id]

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_session)
        mock_db.flush = AsyncMock()

        repo = ChatRepository(mock_db)
        new_id = uuid.uuid4()
        updated = await repo.update_chunk_cache(
            session_id=session_id,
            chunk_ids=[str(existing_id), str(new_id)],
        )

        cached_ids = {str(cid) for cid in updated.retrieved_chunk_ids}
        assert str(existing_id) in cached_ids
        assert str(new_id) in cached_ids
        assert len(updated.retrieved_chunk_ids) == 2

    @pytest.mark.asyncio
    async def test_update_context_summary(self):
        from alphawatch.models.chat import ChatSession
        from alphawatch.repositories.chat import ChatRepository

        session_id = uuid.uuid4()
        mock_session = ChatSession(
            user_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            active_company_ticker="AAPL",
        )
        mock_session.id = session_id
        mock_session.context_summary = None
        mock_session.context_summary_through = 0

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_session)
        mock_db.flush = AsyncMock()

        repo = ChatRepository(mock_db)
        updated = await repo.update_context_summary(
            session_id=session_id,
            summary="We discussed revenue growth.",
            summary_through=12,
        )

        assert updated.context_summary == "We discussed revenue growth."
        assert updated.context_summary_through == 12

    @pytest.mark.asyncio
    async def test_get_messages_returns_list(self):
        from alphawatch.models.chat import ChatSession
        from alphawatch.repositories.chat import ChatRepository

        session_id = uuid.uuid4()
        mock_session = ChatSession(
            user_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            active_company_ticker="AAPL",
        )
        mock_session.id = session_id
        mock_session.messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_session)

        repo = ChatRepository(mock_db)
        msgs = await repo.get_messages(session_id)

        assert len(msgs) == 2

    @pytest.mark.asyncio
    async def test_get_messages_returns_empty_for_missing(self):
        from alphawatch.repositories.chat import ChatRepository

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)

        repo = ChatRepository(mock_db)
        msgs = await repo.get_messages(uuid.uuid4())
        assert msgs == []

    @pytest.mark.asyncio
    async def test_delete_session_enforces_ownership(self):
        from alphawatch.models.chat import ChatSession
        from alphawatch.repositories.chat import ChatRepository

        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        session_id = uuid.uuid4()

        mock_session = ChatSession(
            user_id=owner_id,
            company_id=uuid.uuid4(),
            active_company_ticker="AAPL",
        )
        mock_session.id = session_id

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_session)
        mock_db.delete = AsyncMock()
        mock_db.flush = AsyncMock()

        repo = ChatRepository(mock_db)

        result = await repo.delete_session(session_id, other_id)
        assert result is False
        mock_db.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_session_success(self):
        from alphawatch.models.chat import ChatSession
        from alphawatch.repositories.chat import ChatRepository

        owner_id = uuid.uuid4()
        session_id = uuid.uuid4()

        mock_session = ChatSession(
            user_id=owner_id,
            company_id=uuid.uuid4(),
            active_company_ticker="AAPL",
        )
        mock_session.id = session_id

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_session)
        mock_db.delete = AsyncMock()
        mock_db.flush = AsyncMock()

        repo = ChatRepository(mock_db)
        result = await repo.delete_session(session_id, owner_id)

        assert result is True
        mock_db.delete.assert_called_once_with(mock_session)


# ---------------------------------------------------------------------------
# Pydantic schema tests
# ---------------------------------------------------------------------------


class TestChatSchemas:
    """Tests for chat Pydantic schemas."""

    def test_citation_schema(self):
        from alphawatch.schemas.chat import CitationSchema

        c = CitationSchema(
            chunk_id="c1",
            document_id="d1",
            title="Apple 10-K",
            source_type="edgar_10k",
            source_url="https://example.com",
        )
        assert c.chunk_id == "c1"
        assert c.excerpt == ""

    def test_message_schema_defaults(self):
        from alphawatch.schemas.chat import MessageSchema

        m = MessageSchema(role="user", content="Hello")
        assert m.citations == []
        assert m.suggested_followups == []
        assert m.turn_index == 0

    def test_chat_session_create_request(self):
        from alphawatch.schemas.chat import ChatSessionCreateRequest

        company_id = uuid.uuid4()
        req = ChatSessionCreateRequest(company_id=company_id, ticker="AAPL")
        assert req.company_id == company_id
        assert req.ticker == "AAPL"

    def test_send_message_request(self):
        from alphawatch.schemas.chat import SendMessageRequest

        req = SendMessageRequest(message="What is Apple's P/E?")
        assert req.message == "What is Apple's P/E?"

    def test_sse_token_event(self):
        from alphawatch.schemas.chat import SSETokenEvent

        evt = SSETokenEvent(token="Hello ")
        assert evt.type == "token"
        assert evt.token == "Hello "

    def test_sse_citations_event(self):
        from alphawatch.schemas.chat import CitationSchema, SSECitationsEvent

        cit = CitationSchema(
            chunk_id="c1",
            document_id="d1",
            title="Doc",
            source_type="edgar_10k",
            source_url="",
        )
        evt = SSECitationsEvent(citations=[cit])
        assert evt.type == "citations"
        assert len(evt.citations) == 1

    def test_sse_followups_event(self):
        from alphawatch.schemas.chat import SSEFollowupsEvent

        evt = SSEFollowupsEvent(questions=["Q1?", "Q2?"])
        assert evt.type == "followups"
        assert len(evt.questions) == 2

    def test_sse_done_event(self):
        from alphawatch.schemas.chat import SSEDoneEvent

        evt = SSEDoneEvent(session_id="some-uuid")
        assert evt.type == "done"

    def test_sse_error_event(self):
        from alphawatch.schemas.chat import SSEErrorEvent

        evt = SSEErrorEvent(message="Something went wrong")
        assert evt.type == "error"

    def test_message_history_response(self):
        from alphawatch.schemas.chat import MessageHistoryResponse, MessageSchema

        msg = MessageSchema(role="user", content="Hello")
        session_id = uuid.uuid4()
        resp = MessageHistoryResponse(
            session_id=session_id,
            messages=[msg],
            count=1,
        )
        assert resp.count == 1
        assert resp.session_id == session_id

    def test_chat_session_list_response(self):
        from alphawatch.schemas.chat import ChatSessionListResponse

        resp = ChatSessionListResponse(sessions=[], count=0)
        assert resp.count == 0


# ---------------------------------------------------------------------------
# API routing tests
# ---------------------------------------------------------------------------


class TestChatAPIRouting:
    """Tests for chat API endpoint registration and auth enforcement."""

    def test_create_session_requires_auth(self, client):
        resp = client.post(
            "/api/chat/sessions",
            json={"company_id": str(uuid.uuid4()), "ticker": "AAPL"},
        )
        assert resp.status_code == 401

    def test_list_sessions_requires_auth(self, client):
        resp = client.get(
            "/api/chat/sessions",
            params={"company_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    def test_get_session_requires_auth(self, client):
        resp = client.get(f"/api/chat/sessions/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_delete_session_requires_auth(self, client):
        resp = client.delete(f"/api/chat/sessions/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_get_messages_requires_auth(self, client):
        resp = client.get(f"/api/chat/sessions/{uuid.uuid4()}/messages")
        assert resp.status_code == 401

    def test_send_message_requires_auth(self, client):
        resp = client.post(
            f"/api/chat/sessions/{uuid.uuid4()}/messages",
            json={"message": "Hello"},
        )
        assert resp.status_code == 401

    def test_chat_endpoints_appear_in_openapi(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        assert "/api/chat/sessions" in paths
        assert any("/api/chat/sessions/{session_id}/messages" in p for p in paths)


# ---------------------------------------------------------------------------
# Integration / exports
# ---------------------------------------------------------------------------


class TestChatIntegration:
    """Integration tests: state types, graph, and repository all exportable."""

    def test_chat_state_in_agents_module(self):
        from alphawatch.agents.state import (
            ChatMessage,
            ChatState,
            Citation,
        )

        assert ChatState is not None
        assert ChatMessage is not None
        assert Citation is not None

    def test_chat_graph_builder_exported(self):
        from alphawatch.agents.graphs import build_chat_graph

        assert callable(build_chat_graph)

    def test_chat_repository_exported(self):
        from alphawatch.repositories import ChatRepository

        assert ChatRepository is not None

    def test_all_nodes_importable(self):
        from alphawatch.agents.nodes.chat import (
            check_chunk_cache,
            detect_intent,
            generate_followups,
            generate_response,
            handle_errors,
            maybe_summarize,
            persist_turn,
            prepare_context,
            retrieve_chunks,
        )

        for fn in (
            check_chunk_cache,
            detect_intent,
            generate_followups,
            generate_response,
            handle_errors,
            maybe_summarize,
            persist_turn,
            prepare_context,
            retrieve_chunks,
        ):
            assert callable(fn)

    def test_constants_have_expected_values(self):
        from alphawatch.agents.nodes.chat import (
            CHUNK_CONTEXT_CHARS,
            EDGAR_SOURCE_TYPES,
            MAX_RETRIEVED_CHUNKS,
            RAW_MESSAGE_WINDOW,
            SUMMARY_THRESHOLD,
        )

        assert SUMMARY_THRESHOLD == 20
        assert RAW_MESSAGE_WINDOW == 10
        assert MAX_RETRIEVED_CHUNKS == 8
        assert CHUNK_CONTEXT_CHARS > 0
        assert "edgar_10k" in EDGAR_SOURCE_TYPES
        assert "edgar_10q" in EDGAR_SOURCE_TYPES

    def test_chat_schemas_importable(self):
        from alphawatch.schemas.chat import (
            ChatSessionCreateRequest,
            ChatSessionListResponse,
            ChatSessionResponse,
            CitationSchema,
            MessageHistoryResponse,
            MessageSchema,
            SendMessageRequest,
            SSECitationsEvent,
            SSEDoneEvent,
            SSEErrorEvent,
            SSEFollowupsEvent,
            SSETokenEvent,
        )

        for cls in (
            ChatSessionCreateRequest,
            ChatSessionListResponse,
            ChatSessionResponse,
            CitationSchema,
            MessageHistoryResponse,
            MessageSchema,
            SSECitationsEvent,
            SSEDoneEvent,
            SSEErrorEvent,
            SSEFollowupsEvent,
            SSETokenEvent,
            SendMessageRequest,
        ):
            assert cls is not None
