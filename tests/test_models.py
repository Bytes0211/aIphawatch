"""Tests for SQLAlchemy ORM models."""

from alphawatch.database import Base
from alphawatch.models import (
    AnalystBrief,
    BriefSection,
    ChatSession,
    Company,
    Document,
    DocumentChunk,
    FinancialSnapshot,
    RiskFlag,
    SentimentRecord,
    Tenant,
    User,
    WatchlistEntry,
)


class TestModelRegistration:
    """Verify all models register with Base.metadata."""

    def test_all_12_tables_registered(self):
        tables = Base.metadata.tables
        assert len(tables) == 12

    def test_table_names(self):
        expected = {
            "tenants",
            "users",
            "companies",
            "watchlist",
            "documents",
            "document_chunks",
            "financial_snapshots",
            "sentiment_records",
            "analyst_briefs",
            "brief_sections",
            "chat_sessions",
            "risk_flags",
        }
        assert set(Base.metadata.tables.keys()) == expected


class TestTenantModel:
    """Verify Tenant model structure."""

    def test_tablename(self):
        assert Tenant.__tablename__ == "tenants"

    def test_columns(self):
        cols = {c.name for c in Tenant.__table__.columns}
        assert cols == {"id", "name", "slug", "branding", "config", "created_at", "updated_at"}


class TestUserModel:
    """Verify User model structure."""

    def test_tablename(self):
        assert User.__tablename__ == "users"

    def test_has_tenant_fk(self):
        col = User.__table__.c.tenant_id
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "tenants.id" in fk_targets

    def test_columns(self):
        cols = {c.name for c in User.__table__.columns}
        expected = {
            "id", "tenant_id", "cognito_sub", "email", "role",
            "preferences", "last_login_at", "created_at", "updated_at",
        }
        assert cols == expected


class TestCompanyModel:
    """Verify Company model structure."""

    def test_tablename(self):
        assert Company.__tablename__ == "companies"

    def test_ticker_is_unique(self):
        col = Company.__table__.c.ticker
        assert col.unique is True


class TestWatchlistModel:
    """Verify WatchlistEntry model structure."""

    def test_tablename(self):
        assert WatchlistEntry.__tablename__ == "watchlist"

    def test_user_fk(self):
        fk_targets = {fk.target_fullname for fk in WatchlistEntry.__table__.c.user_id.foreign_keys}
        assert "users.id" in fk_targets

    def test_company_fk(self):
        fk_targets = {fk.target_fullname for fk in WatchlistEntry.__table__.c.company_id.foreign_keys}
        assert "companies.id" in fk_targets


class TestDocumentModels:
    """Verify Document and DocumentChunk model structure."""

    def test_document_tablename(self):
        assert Document.__tablename__ == "documents"

    def test_chunk_tablename(self):
        assert DocumentChunk.__tablename__ == "document_chunks"

    def test_chunk_has_embedding_column(self):
        cols = {c.name for c in DocumentChunk.__table__.columns}
        assert "embedding" in cols

    def test_chunk_has_document_fk(self):
        fk_targets = {fk.target_fullname for fk in DocumentChunk.__table__.c.document_id.foreign_keys}
        assert "documents.id" in fk_targets


class TestFinancialModels:
    """Verify FinancialSnapshot and SentimentRecord structure."""

    def test_snapshot_tablename(self):
        assert FinancialSnapshot.__tablename__ == "financial_snapshots"

    def test_sentiment_tablename(self):
        assert SentimentRecord.__tablename__ == "sentiment_records"

    def test_snapshot_columns(self):
        cols = {c.name for c in FinancialSnapshot.__table__.columns}
        assert "price" in cols
        assert "market_cap" in cols
        assert "pe_ratio" in cols


class TestBriefModels:
    """Verify AnalystBrief and BriefSection structure."""

    def test_brief_tablename(self):
        assert AnalystBrief.__tablename__ == "analyst_briefs"

    def test_section_tablename(self):
        assert BriefSection.__tablename__ == "brief_sections"

    def test_section_has_brief_fk(self):
        fk_targets = {fk.target_fullname for fk in BriefSection.__table__.c.brief_id.foreign_keys}
        assert "analyst_briefs.id" in fk_targets


class TestChatModel:
    """Verify ChatSession structure."""

    def test_tablename(self):
        assert ChatSession.__tablename__ == "chat_sessions"

    def test_columns(self):
        cols = {c.name for c in ChatSession.__table__.columns}
        assert "messages" in cols
        assert "context_summary" in cols
        assert "retrieved_chunk_ids" in cols


class TestRiskFlagModel:
    """Verify RiskFlag structure."""

    def test_tablename(self):
        assert RiskFlag.__tablename__ == "risk_flags"

    def test_document_fk_is_nullable(self):
        col = RiskFlag.__table__.c.document_id
        assert col.nullable is True
