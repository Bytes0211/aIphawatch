"""Add ON DELETE CASCADE to user_id/company_id FKs on chat_sessions and analyst_briefs.

Without CASCADE, deleting a user or company raises a FK violation if chat sessions
or briefs exist for that entity. chat_sessions and analyst_briefs are user-scoped
resources and should be removed automatically when the parent user or company is
deleted.

Revision ID: 002
Revises: 001
Create Date: 2026-03-27
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace FKs on chat_sessions and analyst_briefs with CASCADE variants."""

    # ------------------------------------------------------------------
    # chat_sessions
    # ------------------------------------------------------------------
    op.drop_constraint(
        "chat_sessions_user_id_fkey", "chat_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        "chat_sessions_company_id_fkey", "chat_sessions", type_="foreignkey"
    )
    op.create_foreign_key(
        "chat_sessions_user_id_fkey",
        "chat_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "chat_sessions_company_id_fkey",
        "chat_sessions",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ------------------------------------------------------------------
    # analyst_briefs
    # ------------------------------------------------------------------
    op.drop_constraint(
        "analyst_briefs_user_id_fkey", "analyst_briefs", type_="foreignkey"
    )
    op.drop_constraint(
        "analyst_briefs_company_id_fkey", "analyst_briefs", type_="foreignkey"
    )
    op.create_foreign_key(
        "analyst_briefs_user_id_fkey",
        "analyst_briefs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "analyst_briefs_company_id_fkey",
        "analyst_briefs",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Revert to plain FKs (no CASCADE) on chat_sessions and analyst_briefs."""

    # ------------------------------------------------------------------
    # analyst_briefs — restore plain FKs
    # ------------------------------------------------------------------
    op.drop_constraint(
        "analyst_briefs_user_id_fkey", "analyst_briefs", type_="foreignkey"
    )
    op.drop_constraint(
        "analyst_briefs_company_id_fkey", "analyst_briefs", type_="foreignkey"
    )
    op.create_foreign_key(
        "analyst_briefs_user_id_fkey",
        "analyst_briefs",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "analyst_briefs_company_id_fkey",
        "analyst_briefs",
        "companies",
        ["company_id"],
        ["id"],
    )

    # ------------------------------------------------------------------
    # chat_sessions — restore plain FKs
    # ------------------------------------------------------------------
    op.drop_constraint(
        "chat_sessions_user_id_fkey", "chat_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        "chat_sessions_company_id_fkey", "chat_sessions", type_="foreignkey"
    )
    op.create_foreign_key(
        "chat_sessions_user_id_fkey",
        "chat_sessions",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "chat_sessions_company_id_fkey",
        "chat_sessions",
        "companies",
        ["company_id"],
        ["id"],
    )
