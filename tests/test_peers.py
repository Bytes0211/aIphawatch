"""Tests for PeersChips + competitor detection: node, graph routing, state."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from alphawatch.agents.state import ChatState


# ---------------------------------------------------------------------------
# competitor_lookup node
# ---------------------------------------------------------------------------


class TestCompetitorLookup:
    """Tests for the competitor_lookup chat node."""

    @pytest.mark.asyncio
    async def test_empty_comparison_entity_returns_empty(self):
        from alphawatch.agents.nodes.chat import competitor_lookup

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "comparison_entity": "",
            "errors": [],
        }
        result = await competitor_lookup(state)
        assert result["competitor_data"] == {}

    @pytest.mark.asyncio
    async def test_missing_comparison_entity_returns_empty(self):
        from alphawatch.agents.nodes.chat import competitor_lookup

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "errors": [],
        }
        result = await competitor_lookup(state)
        assert result["competitor_data"] == {}

    @pytest.mark.asyncio
    async def test_ticker_not_found_returns_unavailable(self):
        from alphawatch.agents.nodes.chat import competitor_lookup

        mock_company_repo = AsyncMock()
        mock_company_repo.get_by_ticker = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "comparison_entity": "UNKNOWN",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.chat.CompanyRepository",
                return_value=mock_company_repo,
            ),
        ):
            result = await competitor_lookup(state)

        assert result["competitor_data"]["available"] is False
        assert "UNKNOWN" in result["competitor_data"]["ticker"]

    @pytest.mark.asyncio
    async def test_found_with_snapshot(self):
        from alphawatch.agents.nodes.chat import competitor_lookup
        from decimal import Decimal

        mock_company = Mock()
        mock_company.id = uuid.uuid4()
        mock_company.ticker = "MSFT"
        mock_company.name = "Microsoft Corp."
        mock_company.sector = "Technology"

        mock_snapshot = Mock()
        mock_snapshot.snapshot_date = "2026-03-26"
        mock_snapshot.price = Decimal("420.50")
        mock_snapshot.price_change_pct = Decimal("1.2")
        mock_snapshot.market_cap = 3100000000000
        mock_snapshot.pe_ratio = Decimal("35.0")
        mock_snapshot.debt_to_equity = Decimal("0.45")
        mock_snapshot.analyst_rating = "Buy"

        mock_company_repo = AsyncMock()
        mock_company_repo.get_by_ticker = AsyncMock(return_value=mock_company)

        mock_fin_repo = AsyncMock()
        mock_fin_repo.get_latest = AsyncMock(return_value=mock_snapshot)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "comparison_entity": "MSFT",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.chat.CompanyRepository",
                return_value=mock_company_repo,
            ),
            patch(
                "alphawatch.agents.nodes.chat.FinancialSnapshotRepository",
                return_value=mock_fin_repo,
            ),
        ):
            result = await competitor_lookup(state)

        data = result["competitor_data"]
        assert data["available"] is True
        assert data["ticker"] == "MSFT"
        assert data["price"] == 420.50
        assert data["pe_ratio"] == 35.0

    @pytest.mark.asyncio
    async def test_found_without_snapshot(self):
        from alphawatch.agents.nodes.chat import competitor_lookup

        mock_company = Mock()
        mock_company.id = uuid.uuid4()
        mock_company.ticker = "GOOG"
        mock_company.name = "Alphabet Inc."
        mock_company.sector = "Technology"

        mock_company_repo = AsyncMock()
        mock_company_repo.get_by_ticker = AsyncMock(return_value=mock_company)

        mock_fin_repo = AsyncMock()
        mock_fin_repo.get_latest = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "comparison_entity": "GOOG",
            "errors": [],
        }

        with (
            patch(
                "alphawatch.agents.nodes.chat.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "alphawatch.agents.nodes.chat.CompanyRepository",
                return_value=mock_company_repo,
            ),
            patch(
                "alphawatch.agents.nodes.chat.FinancialSnapshotRepository",
                return_value=mock_fin_repo,
            ),
        ):
            result = await competitor_lookup(state)

        data = result["competitor_data"]
        assert data["available"] is True
        assert data["ticker"] == "GOOG"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_error_returns_empty_data(self):
        from alphawatch.agents.nodes.chat import competitor_lookup

        state: ChatState = {
            "company_id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "comparison_entity": "MSFT",
            "errors": [],
        }

        with patch(
            "alphawatch.agents.nodes.chat.async_session_factory",
            side_effect=RuntimeError("DB down"),
        ):
            result = await competitor_lookup(state)

        assert result["competitor_data"] == {}
        assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# Graph routing
# ---------------------------------------------------------------------------


class TestComparisonRouting:
    """Test that comparison routing is wired correctly in ChatGraph."""

    def test_route_by_comparison_with_entity(self):
        from alphawatch.agents.graphs.chat import _route_by_comparison

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "comparison_entity": "MSFT",
        }
        assert _route_by_comparison(state) == "competitor_lookup"

    def test_route_by_comparison_without_entity(self):
        from alphawatch.agents.graphs.chat import _route_by_comparison

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "comparison_entity": "",
        }
        assert _route_by_comparison(state) == "generate_response"

    def test_cache_hit_with_comparison_routes_to_competitor(self):
        """Cache hit + comparison_entity should NOT skip competitor_lookup."""
        from alphawatch.agents.graphs.chat import _route_by_cache

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "cache_hit": True,
            "comparison_entity": "MSFT",
        }
        assert _route_by_cache(state) == "competitor_lookup"

    def test_cache_hit_without_comparison_routes_to_response(self):
        """Cache hit without comparison should go straight to generate_response."""
        from alphawatch.agents.graphs.chat import _route_by_cache

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "cache_hit": True,
            "comparison_entity": "",
        }
        assert _route_by_cache(state) == "generate_response"

    def test_route_by_comparison_missing_key(self):
        from alphawatch.agents.graphs.chat import _route_by_comparison

        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
        }
        assert _route_by_comparison(state) == "generate_response"

    def test_graph_has_competitor_lookup_node(self):
        from alphawatch.agents.graphs.chat import build_chat_graph

        graph = build_chat_graph()
        node_names = set(graph.get_graph().nodes.keys())
        assert "competitor_lookup" in node_names

    def test_graph_compiles_with_competitor_node(self):
        from alphawatch.agents.graphs.chat import build_chat_graph

        graph = build_chat_graph()
        assert graph is not None
        assert hasattr(graph, "ainvoke")


# ---------------------------------------------------------------------------
# ChatState competitor_data field
# ---------------------------------------------------------------------------


class TestChatStateCompetitorData:
    """Test that ChatState supports the competitor_data field."""

    def test_state_with_competitor_data(self):
        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
            "competitor_data": {
                "ticker": "MSFT",
                "name": "Microsoft Corp.",
                "available": True,
                "price": 420.50,
            },
        }
        assert state["competitor_data"]["ticker"] == "MSFT"

    def test_state_without_competitor_data(self):
        state: ChatState = {
            "company_id": "c-1",
            "ticker": "AAPL",
        }
        assert "competitor_data" not in state
