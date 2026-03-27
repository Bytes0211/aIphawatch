"""Tests for dashboard endpoint: schemas, change_score, repository, auth, routing."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from alphawatch.repositories.dashboard import DashboardRepository, _compute_change_score
from alphawatch.schemas.dashboard import CompanyCard, DashboardResponse


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
_NOW = datetime(2026, 3, 27, tzinfo=timezone.utc)


class TestCompanyCardSchema:
    """Test CompanyCard Pydantic schema."""

    def test_full_card(self):
        card = CompanyCard(
            company_id=_UUID,
            ticker="AAPL",
            name="Apple Inc.",
            sector="Technology",
            price=182.5,
            price_change_pct=2.3,
            sentiment_score=42,
            sentiment_delta=5,
            new_filings_count=2,
            risk_flag_count=1,
            risk_flag_max_severity="high",
            last_updated_at=_NOW,
            brief_id=_UUID,
            change_score=120.6,
        )
        assert card.ticker == "AAPL"
        assert card.change_score == 120.6

    def test_minimal_card(self):
        card = CompanyCard(
            company_id=_UUID,
            ticker="MSFT",
            name="Microsoft Corp.",
        )
        assert card.price is None
        assert card.change_score == 0.0
        assert card.new_filings_count == 0

    def test_model_dump(self):
        card = CompanyCard(
            company_id=_UUID,
            ticker="AAPL",
            name="Apple Inc.",
        )
        d = card.model_dump()
        assert "ticker" in d
        assert "change_score" in d


class TestDashboardResponseSchema:
    """Test DashboardResponse schema."""

    def test_empty_dashboard(self):
        resp = DashboardResponse(
            cards=[],
            as_of=_NOW,
            total=0,
        )
        assert resp.total == 0
        assert resp.time_range == "7d"

    def test_with_cards(self):
        card = CompanyCard(
            company_id=_UUID,
            ticker="AAPL",
            name="Apple Inc.",
            change_score=100.0,
        )
        resp = DashboardResponse(
            cards=[card],
            as_of=_NOW,
            time_range="24h",
            total=1,
        )
        assert resp.total == 1
        assert resp.time_range == "24h"


# ---------------------------------------------------------------------------
# Change score computation
# ---------------------------------------------------------------------------


class TestChangeScore:
    """Test _compute_change_score function."""

    def test_all_zeros(self):
        assert _compute_change_score(0, 0, None, None) == 0.0

    def test_filings_weight(self):
        # 2 filings × 30 = 60
        assert _compute_change_score(2, 0, None, None) == 60.0

    def test_risk_weight(self):
        # 3 risks × 25 = 75
        assert _compute_change_score(0, 3, None, None) == 75.0

    def test_price_weight(self):
        # |5.0| × 2 = 10
        assert _compute_change_score(0, 0, 5.0, None) == 10.0

    def test_negative_price_uses_abs(self):
        # |-3.5| × 2 = 7.0
        assert _compute_change_score(0, 0, -3.5, None) == 7.0

    def test_sentiment_weight(self):
        # |42| × 1 = 42
        assert _compute_change_score(0, 0, None, 42) == 42.0

    def test_composite(self):
        # 1×30 + 2×25 + |3.0|×2 + |10|×1 = 30+50+6+10 = 96
        assert _compute_change_score(1, 2, 3.0, 10) == 96.0


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


class TestDashboardEndpointAuth:
    """Test dashboard endpoint enforces authentication."""

    async def test_dashboard_requires_auth(self, async_client):
        resp = await async_client.get("/api/dashboard")
        assert resp.status_code == 401

    async def test_dashboard_with_time_range_requires_auth(self, async_client):
        resp = await async_client.get("/api/dashboard?time_range=24h")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Routing / OpenAPI
# ---------------------------------------------------------------------------


class TestDashboardEndpointRouting:
    """Test dashboard endpoint is registered and routable."""

    async def test_dashboard_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/dashboard" in paths

    async def test_dashboard_is_get(self, async_client):
        resp = await async_client.get("/openapi.json")
        methods = resp.json()["paths"]["/api/dashboard"]
        assert "get" in methods

    async def test_dashboard_has_time_range_param(self, async_client):
        resp = await async_client.get("/openapi.json")
        endpoint = resp.json()["paths"]["/api/dashboard"]["get"]
        param_names = [p["name"] for p in endpoint.get("parameters", [])]
        assert "time_range" in param_names

    async def test_time_range_is_enum_restricted(self, async_client):
        """time_range is declared as a Literal enum in the OpenAPI schema.

        Auth middleware intercepts unauthenticated requests before FastAPI
        validates query params, so the 422 only fires for authenticated calls.
        Here we verify the contract via the generated schema instead.
        """
        resp = await async_client.get("/openapi.json")
        endpoint = resp.json()["paths"]["/api/dashboard"]["get"]
        param = next(
            p for p in endpoint["parameters"] if p["name"] == "time_range"
        )
        # FastAPI translates Literal["24h", "7d", "30d"] → schema with enum
        schema = param.get("schema", {})
        assert "enum" in schema
        assert set(schema["enum"]) == {"24h", "7d", "30d"}


# ---------------------------------------------------------------------------
# DashboardRepository unit tests
# ---------------------------------------------------------------------------

_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_CID1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
_CID2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
_BRIEF_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_REPO_NOW = datetime(2026, 3, 27, tzinfo=timezone.utc)


def _make_company(cid: uuid.UUID, ticker: str, name: str) -> MagicMock:
    company = MagicMock()
    company.id = cid
    company.ticker = ticker
    company.name = name
    company.sector = "Technology"
    return company


def _all_result(rows: list) -> MagicMock:
    r = MagicMock()
    r.all.return_value = rows
    return r


def _mappings_result(rows: list) -> MagicMock:
    r = MagicMock()
    r.mappings.return_value = rows
    return r


def _make_session(*execute_returns) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=list(execute_returns))
    return session


class TestDashboardRepositoryEmptyWatchlist:
    """DashboardRepository returns [] when watchlist is empty."""

    @pytest.mark.asyncio
    async def test_empty_watchlist_returns_empty_list(self):
        session = _make_session(_all_result([]))
        repo = DashboardRepository(session)
        cards = await repo.get_dashboard_cards(_USER_ID, days=7)
        assert cards == []
        assert session.execute.call_count == 1


class TestDashboardRepositoryHappyPath:
    """DashboardRepository builds and sorts cards correctly."""

    def _make_execute_seq(
        self,
        *,
        cid: uuid.UUID,
        user_id: uuid.UUID,
        price: float = 182.5,
        price_change_pct: float = 2.0,
        sentiment_current: int = 40,
        sentiment_prior: int = 30,
        filings_count: int = 2,
        risk_count: int = 1,
        max_sev_rank: int = 3,
        brief_id: uuid.UUID | None = _BRIEF_ID,
    ):
        company = _make_company(cid, "AAPL", "Apple Inc.")
        entry = MagicMock()

        snap_row = MagicMock()
        snap_row.company_id = cid
        snap_row.price = price
        snap_row.price_change_pct = price_change_pct
        snap_row.created_at = _REPO_NOW

        sent_curr_row = MagicMock()
        sent_curr_row.company_id = cid
        sent_curr_row.avg_score = sentiment_current

        sent_prior_row = MagicMock()
        sent_prior_row.company_id = cid
        sent_prior_row.avg_score = sentiment_prior

        filings_row = MagicMock()
        filings_row.company_id = cid
        filings_row.cnt = filings_count

        risk_row = MagicMock()
        risk_row.company_id = cid
        risk_row.cnt = risk_count
        risk_row.max_sev_rank = max_sev_rank

        brief_rows = []
        if brief_id:
            brief_row = MagicMock()
            brief_row.company_id = cid
            brief_row.brief_id = brief_id
            brief_rows = [brief_row]

        return [
            _all_result([(entry, company)]),
            _mappings_result([snap_row]),
            _mappings_result([sent_curr_row]),
            _mappings_result([sent_prior_row]),
            _mappings_result([filings_row]),
            _mappings_result([risk_row]),
            _mappings_result(brief_rows),
        ]

    @pytest.mark.asyncio
    async def test_returns_one_card_with_correct_fields(self):
        session = _make_session(*self._make_execute_seq(cid=_CID1, user_id=_USER_ID))
        repo = DashboardRepository(session)
        cards = await repo.get_dashboard_cards(_USER_ID, days=7)

        assert len(cards) == 1
        card = cards[0]
        assert card.ticker == "AAPL"
        assert card.company_id == _CID1
        assert card.price == 182.5
        assert card.price_change_pct == 2.0
        assert card.sentiment_score == 40
        assert card.sentiment_delta == 10   # 40 - 30
        assert card.new_filings_count == 2
        assert card.risk_flag_count == 1
        assert card.risk_flag_max_severity == "high"  # rank 3
        assert card.brief_id == _BRIEF_ID

    @pytest.mark.asyncio
    async def test_change_score_is_calculated(self):
        session = _make_session(
            *self._make_execute_seq(
                cid=_CID1,
                user_id=_USER_ID,
                price_change_pct=5.0,
                filings_count=1,
                risk_count=2,
                max_sev_rank=2,
                sentiment_current=42,
                sentiment_prior=32,
            )
        )
        repo = DashboardRepository(session)
        cards = await repo.get_dashboard_cards(_USER_ID, days=7)
        # 1×30 + 2×25 + |5.0|×2 + |10|×1 = 30+50+10+10 = 100
        assert cards[0].change_score == 100.0

    @pytest.mark.asyncio
    async def test_cards_sorted_by_change_score_descending(self):
        company1 = _make_company(_CID1, "AAPL", "Apple Inc.")
        company2 = _make_company(_CID2, "MSFT", "Microsoft Corp.")
        entry1, entry2 = MagicMock(), MagicMock()

        snap1, snap2 = MagicMock(), MagicMock()
        snap1.company_id = _CID1
        snap1.price = 182.5
        snap1.price_change_pct = 1.0
        snap1.created_at = _REPO_NOW
        snap2.company_id = _CID2
        snap2.price = 420.0
        snap2.price_change_pct = 0.5
        snap2.created_at = _REPO_NOW

        def _sent(cid):
            m = MagicMock(); m.company_id = cid; m.avg_score = 0; return m

        def _filings(cid, cnt):
            m = MagicMock(); m.company_id = cid; m.cnt = cnt; return m

        def _risk(cid, cnt, sev):
            m = MagicMock(); m.company_id = cid; m.cnt = cnt; m.max_sev_rank = sev; return m

        def _brief(cid):
            m = MagicMock(); m.company_id = cid; m.brief_id = _BRIEF_ID; return m

        session = _make_session(
            _all_result([(entry1, company1), (entry2, company2)]),
            _mappings_result([snap1, snap2]),
            _mappings_result([_sent(_CID1), _sent(_CID2)]),
            _mappings_result([_sent(_CID1), _sent(_CID2)]),
            # AAPL: 3 filings (score 90), MSFT: 0
            _mappings_result([_filings(_CID1, 3), _filings(_CID2, 0)]),
            _mappings_result([_risk(_CID1, 0, None), _risk(_CID2, 0, None)]),
            _mappings_result([_brief(_CID1), _brief(_CID2)]),
        )
        repo = DashboardRepository(session)
        cards = await repo.get_dashboard_cards(_USER_ID, days=7)

        assert len(cards) == 2
        assert cards[0].ticker == "AAPL"
        assert cards[1].ticker == "MSFT"


class TestDashboardRepositoryMissingData:
    """DashboardRepository handles missing optional data gracefully."""

    @pytest.mark.asyncio
    async def test_missing_snapshot_sets_none_price(self):
        company = _make_company(_CID1, "AAPL", "Apple Inc.")
        entry = MagicMock()

        session = _make_session(
            _all_result([(entry, company)]),
            _mappings_result([]),
            _mappings_result([]),
            _mappings_result([]),
            _mappings_result([]),
            _mappings_result([]),
            _mappings_result([]),
        )
        repo = DashboardRepository(session)
        cards = await repo.get_dashboard_cards(_USER_ID, days=7)

        assert len(cards) == 1
        card = cards[0]
        assert card.price is None
        assert card.price_change_pct is None
        assert card.sentiment_score is None
        assert card.sentiment_delta is None

    @pytest.mark.asyncio
    async def test_missing_brief_sets_brief_id_none(self):
        company = _make_company(_CID1, "AAPL", "Apple Inc.")
        entry = MagicMock()

        session = _make_session(
            _all_result([(entry, company)]),
            _mappings_result([]),
            _mappings_result([]),
            _mappings_result([]),
            _mappings_result([]),
            _mappings_result([]),
            _mappings_result([]),
        )
        repo = DashboardRepository(session)
        cards = await repo.get_dashboard_cards(_USER_ID, days=7)
        assert cards[0].brief_id is None

    @pytest.mark.asyncio
    async def test_severity_rank_mapping(self):
        """Severity integer ranks map to the correct string label."""
        for rank, label in [(4, "critical"), (3, "high"), (2, "medium"), (1, "low")]:
            company = _make_company(_CID1, "AAPL", "Apple Inc.")
            entry = MagicMock()

            risk_row = MagicMock()
            risk_row.company_id = _CID1
            risk_row.cnt = 1
            risk_row.max_sev_rank = rank

            session = _make_session(
                _all_result([(entry, company)]),
                _mappings_result([]),
                _mappings_result([]),
                _mappings_result([]),
                _mappings_result([]),
                _mappings_result([risk_row]),
                _mappings_result([]),
            )
            repo = DashboardRepository(session)
            cards = await repo.get_dashboard_cards(_USER_ID, days=7)
            assert cards[0].risk_flag_max_severity == label, (
                f"rank {rank} should map to '{label}'"
            )

    @pytest.mark.asyncio
    async def test_risk_flags_are_all_time_not_windowed(self):
        """_batch_risk_summary does NOT receive a :days param — documents intentional all-time behaviour."""
        company = _make_company(_CID1, "AAPL", "Apple Inc.")
        entry = MagicMock()
        calls: list[dict] = []

        async def capture_execute(sql, params=None):
            calls.append({"sql": str(sql), "params": params or {}})
            r = MagicMock()
            r.all.return_value = [(entry, company)] if len(calls) == 1 else []
            r.mappings.return_value = []
            return r

        session = AsyncMock()
        session.execute = capture_execute

        repo = DashboardRepository(session)
        await repo.get_dashboard_cards(_USER_ID, days=7)

        risk_call = calls[5]
        assert "risk_flags" in risk_call["sql"]
        assert "days" not in risk_call["params"]
