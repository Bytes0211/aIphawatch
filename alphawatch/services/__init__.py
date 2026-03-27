"""Service layer for external API clients."""

from alphawatch.services.bedrock import BedrockClient
from alphawatch.services.chunker import chunk_text
from alphawatch.services.edgar import EdgarClient
from alphawatch.services.embeddings import EmbeddingsService
from alphawatch.services.news import NewsArticle, NewsClient

__all__ = [
    "BedrockClient",
    "EdgarClient",
    "EmbeddingsService",
    "NewsArticle",
    "NewsClient",
    "chunk_text",
]
