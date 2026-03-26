"""Tenant ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alphawatch.database import Base


class Tenant(Base):
    """Multi-tenant organization.

    Attributes:
        id: Primary key UUID.
        name: Organization display name.
        slug: URL-safe identifier for subdomain routing.
        branding: JSONB with logo_url, primary_color, accent_color.
        config: JSONB with watchlist_limit, thresholds, schedule.
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    branding: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"), onupdate=text("NOW()"))

    users: Mapped[list["User"]] = relationship(back_populates="tenant")  # noqa: F821
