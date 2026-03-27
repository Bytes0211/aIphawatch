"""Repository layer for data access."""

from alphawatch.repositories.briefs import BriefRepository
from alphawatch.repositories.chat import ChatRepository
from alphawatch.repositories.chunks import ChunkRepository
from alphawatch.repositories.companies import CompanyRepository
from alphawatch.repositories.documents import DocumentRepository
from alphawatch.repositories.financial import FinancialSnapshotRepository
from alphawatch.repositories.sentiment import SentimentRepository
from alphawatch.repositories.watchlist import WatchlistRepository

__all__ = [
    "BriefRepository",
    "ChatRepository",
    "ChunkRepository",
    "CompanyRepository",
    "DocumentRepository",
    "FinancialSnapshotRepository",
    "SentimentRepository",
    "WatchlistRepository",
]
