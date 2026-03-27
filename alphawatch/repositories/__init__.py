"""Repository layer for data access."""

from alphawatch.repositories.companies import CompanyRepository
from alphawatch.repositories.documents import DocumentRepository
from alphawatch.repositories.sentiment import SentimentRepository
from alphawatch.repositories.watchlist import WatchlistRepository

__all__ = [
    "CompanyRepository",
    "DocumentRepository",
    "SentimentRepository",
    "WatchlistRepository",
]
