"""SQLAlchemy ORM models — import all models so Alembic metadata is complete."""

from alphawatch.models.tenant import Tenant
from alphawatch.models.user import User
from alphawatch.models.company import Company
from alphawatch.models.watchlist import WatchlistEntry
from alphawatch.models.document import Document, DocumentChunk
from alphawatch.models.financial import FinancialSnapshot, SentimentRecord
from alphawatch.models.brief import AnalystBrief, BriefSection
from alphawatch.models.chat import ChatSession
from alphawatch.models.risk import RiskFlag

__all__ = [
    "Tenant",
    "User",
    "Company",
    "WatchlistEntry",
    "Document",
    "DocumentChunk",
    "FinancialSnapshot",
    "SentimentRecord",
    "AnalystBrief",
    "BriefSection",
    "ChatSession",
    "RiskFlag",
]
