"""Initial schema: all tables, indexes, pgvector HNSW, RLS policies.

Revision ID: 001
Revises: None
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Extensions
    # -------------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # -------------------------------------------------------------------------
    # Core tables
    # -------------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("branding", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cognito_sub", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("preferences", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("cognito_sub", name="uq_users_cognito_sub"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        sa.CheckConstraint("role IN ('admin', 'analyst', 'viewer')", name="ck_users_role"),
    )
    op.create_index("idx_users_tenant", "users", ["tenant_id"])

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("cik", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("ticker", name="uq_companies_ticker"),
    )
    op.create_index("idx_companies_ticker", "companies", ["ticker"])
    op.create_index("idx_companies_cik", "companies", ["cik"])

    op.create_table(
        "watchlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("alert_thresholds", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("user_id", "company_id", name="uq_watchlist_user_company"),
    )
    op.create_index("idx_watchlist_user", "watchlist", ["user_id"])
    op.create_index("idx_watchlist_company", "watchlist", ["company_id"])

    # -------------------------------------------------------------------------
    # Ingestion tables
    # -------------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("company_id", "content_hash", name="uq_documents_company_hash"),
        sa.CheckConstraint(
            "source_type IN ('edgar_10k', 'edgar_10q', 'edgar_8k', 'news', 'upload')",
            name="ck_documents_source_type",
        ),
    )
    op.create_index("idx_documents_company", "documents", ["company_id"])
    op.create_index("idx_documents_source_type", "documents", ["company_id", "source_type"])
    op.create_index("idx_documents_ingested", "documents", ["ingested_at"])

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
    )
    op.create_index("idx_chunks_company", "document_chunks", ["company_id"])
    op.create_index("idx_chunks_document", "document_chunks", ["document_id"])

    # -------------------------------------------------------------------------
    # Financial & sentiment tables
    # -------------------------------------------------------------------------
    op.create_table(
        "financial_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=True),
        sa.Column("price_change_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(10, 2), nullable=True),
        sa.Column("debt_to_equity", sa.Numeric(10, 4), nullable=True),
        sa.Column("analyst_rating", sa.Text(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("company_id", "snapshot_date", name="uq_snapshots_company_date"),
    )
    op.create_index("idx_snapshots_company", "financial_snapshots", ["company_id", "snapshot_date"])

    op.create_table(
        "sentiment_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint("score BETWEEN -100 AND 100", name="ck_sentiment_score_range"),
    )
    op.create_index("idx_sentiment_company", "sentiment_records", ["company_id", "scored_at"])

    # -------------------------------------------------------------------------
    # Brief tables
    # -------------------------------------------------------------------------
    op.create_table(
        "analyst_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_briefs_user_company", "analyst_briefs", ["user_id", "company_id", "generated_at"])

    op.create_table(
        "brief_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyst_briefs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_type", sa.Text(), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("brief_id", "section_type", name="uq_brief_sections_type"),
        sa.CheckConstraint(
            "section_type IN ('header', 'snapshot', 'what_changed', 'risk_flags', "
            "'sentiment', 'executive_summary', 'sources', 'suggested_followups')",
            name="ck_brief_sections_type",
        ),
    )
    op.create_index("idx_brief_sections_brief", "brief_sections", ["brief_id", "section_order"])

    # -------------------------------------------------------------------------
    # Chat & risk tables
    # -------------------------------------------------------------------------
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("active_company_ticker", sa.Text(), nullable=False),
        sa.Column("messages", postgresql.ARRAY(postgresql.JSONB()), server_default="{}", nullable=False),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("context_summary_through", sa.Integer(), server_default=sa.text("0")),
        sa.Column("retrieved_chunk_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_sessions_user_company", "chat_sessions", ["user_id", "company_id", "updated_at"])

    op.create_table(
        "risk_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("flag_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "flag_type IN ('covenant', 'litigation', 'guidance_cut', 'insider_sell', 'schema_drift')",
            name="ck_risk_flags_type",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_risk_flags_severity",
        ),
    )
    op.create_index("idx_risk_flags_company", "risk_flags", ["company_id", "detected_at"])

    # -------------------------------------------------------------------------
    # HNSW vector index for ANN search (pgvector)
    # -------------------------------------------------------------------------
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # -------------------------------------------------------------------------
    # Row-Level Security policies
    # -------------------------------------------------------------------------
    # users: direct tenant_id column
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_users ON users "
        "USING (tenant_id = current_setting('app.tenant_id')::UUID)"
    )

    # watchlist: tenant scope via user_id -> users.tenant_id
    op.execute("ALTER TABLE watchlist ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_watchlist ON watchlist "
        "USING (user_id IN ("
        "  SELECT id FROM users WHERE tenant_id = current_setting('app.tenant_id')::UUID"
        "))"
    )

    # analyst_briefs: tenant scope via user_id -> users.tenant_id
    op.execute("ALTER TABLE analyst_briefs ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_briefs ON analyst_briefs "
        "USING (user_id IN ("
        "  SELECT id FROM users WHERE tenant_id = current_setting('app.tenant_id')::UUID"
        "))"
    )

    # chat_sessions: tenant scope via user_id -> users.tenant_id
    op.execute("ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_chat ON chat_sessions "
        "USING (user_id IN ("
        "  SELECT id FROM users WHERE tenant_id = current_setting('app.tenant_id')::UUID"
        "))"
    )


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_chat ON chat_sessions")
    op.execute("ALTER TABLE chat_sessions DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_briefs ON analyst_briefs")
    op.execute("ALTER TABLE analyst_briefs DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_watchlist ON watchlist")
    op.execute("ALTER TABLE watchlist DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_users ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    # Drop HNSW index
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")

    # Drop tables in reverse dependency order
    op.drop_table("risk_flags")
    op.drop_table("chat_sessions")
    op.drop_table("brief_sections")
    op.drop_table("analyst_briefs")
    op.drop_table("sentiment_records")
    op.drop_table("financial_snapshots")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("watchlist")
    op.drop_table("companies")
    op.drop_table("users")
    op.drop_table("tenants")

    op.execute("DROP EXTENSION IF EXISTS vector")
