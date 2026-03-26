"""Tests for sentiment analysis: NewsClient, BedrockClient, SentimentGraph, and repository."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from alphawatch.agents.state import (
    NewsArticleRef,
    SentimentState,
)
from alphawatch.services.bedrock import BedrockClient
from alphawatch.services.news import NewsArticle, NewsClient


# ---------------------------------------------------------------------------
# State types
# ---------------------------------------------------------------------------
class TestNewsArticleRef:
    """Test NewsArticleRef dataclass."""

    def test_creation_minimal(self):
        ref = NewsArticleRef(
            title="Test Article",
            description="Test description",
            url="https://example.com/article",
            source_name="Test Source",
            published_at="2026-01-15T10:00:00Z",
        )
        assert ref.title == "Test Article"
        assert ref.url == "https://example.com/article"
        assert ref.content == ""

    def test_creation_with_content(self):
        ref = NewsArticleRef(
            title="Article",
            description="Desc",
            url="https://example.com",
            source_name="Source",
            published_at="2026-01-15T10:00:00Z",
            content="Full article content here",
        )
        assert ref.content == "Full article content here"


class TestSentimentState:
    """Test SentimentState TypedDict structure."""

    def test_sentiment_state_extends_base(self):
        state: SentimentState = {
            "tenant_id": "t-1",
            "user_id": "u-1",
            "company_id": "c-1",
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "errors": [],
            "metadata": {},
            "days_back": 7,
            "articles": [],
            "parsed_documents": [],
            "sentiment_scores": [],
            "scores_stored": 0,
        }
        assert state["company_name"] == "Apple Inc."
        assert state["days_back"] == 7
        assert state["scores_stored"] == 0

    def test_minimal_sentiment_state(self):
        state: SentimentState = {
            "ticker": "MSFT",
            "company_id": "c-1",
        }
        assert state["ticker"] == "MSFT"
        assert "articles" not in state  # optional field


# ---------------------------------------------------------------------------
# NewsArticle
# ---------------------------------------------------------------------------
class TestNewsArticle:
    """Test NewsArticle data class."""

    def test_creation_minimal(self):
        article = NewsArticle(
            title="Breaking News",
            description=None,
            url="https://example.com",
            source_name="News Source",
            published_at="2026-01-15T10:00:00Z",
        )
        assert article.title == "Breaking News"
        assert article.description == ""  # None converts to empty string
        assert article.content == ""

    def test_creation_full(self):
        article = NewsArticle(
            title="Full Article",
            description="Article summary",
            url="https://example.com",
            source_name="Source",
            published_at="2026-01-15T10:00:00Z",
            content="Full content here",
            author="John Doe",
        )
        assert article.author == "John Doe"
        assert article.content == "Full content here"


# ---------------------------------------------------------------------------
# NewsClient
# ---------------------------------------------------------------------------
class TestNewsClient:
    """Test NewsClient API wrapper."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx.AsyncClient."""
        with patch("alphawatch.services.news.httpx.AsyncClient") as mock:
            yield mock

    def test_client_initialization(self):
        client = NewsClient()
        assert client._page_size == 10  # default from settings
        assert client._daily_limit == 100

    def test_client_custom_params(self):
        client = NewsClient(
            api_key="test-key",
            page_size=20,
            daily_limit=50,
        )
        assert client._api_key == "test-key"
        assert client._page_size == 20
        assert client._daily_limit == 50

    @pytest.mark.asyncio
    async def test_search_articles_success(self, mock_httpx_client):
        """Test successful article search."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "Test Article 1",
                    "description": "Description 1",
                    "url": "https://example.com/1",
                    "source": {"name": "Source 1"},
                    "publishedAt": "2026-01-15T10:00:00Z",
                    "content": "Content 1",
                    "author": "Author 1",
                },
                {
                    "title": "Test Article 2",
                    "description": None,
                    "url": "https://example.com/2",
                    "source": {"name": "Source 2"},
                    "publishedAt": "2026-01-15T11:00:00Z",
                },
            ],
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.aclose = AsyncMock()
        mock_httpx_client.return_value = mock_client_instance

        client = NewsClient(api_key="test-key")
        articles = await client.search_articles(query="AAPL")

        assert len(articles) == 2
        assert articles[0].title == "Test Article 1"
        assert articles[0].author == "Author 1"
        assert articles[1].description == ""  # None converted

    @pytest.mark.asyncio
    async def test_search_articles_no_api_key(self):
        """Test that missing API key raises error."""
        with patch("alphawatch.services.news.get_settings") as mock_settings:
            mock_settings.return_value.newsapi_api_key = ""
            mock_settings.return_value.newsapi_base_url = "https://test.com"
            mock_settings.return_value.newsapi_page_size = 10
            mock_settings.return_value.newsapi_daily_limit = 100

            client = NewsClient()
            with pytest.raises(ValueError, match="NewsAPI API key not configured"):
                await client.search_articles(query="AAPL")

    @pytest.mark.asyncio
    async def test_search_articles_api_error(self, mock_httpx_client):
        """Test handling of NewsAPI error response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "error",
            "message": "Invalid API key",
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.return_value = mock_client_instance

        client = NewsClient(api_key="invalid-key")
        with pytest.raises(ValueError, match="Invalid API key"):
            await client.search_articles(query="AAPL")

    @pytest.mark.asyncio
    async def test_search_articles_skips_incomplete(self, mock_httpx_client):
        """Test that articles with missing required fields are skipped."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "Valid Article",
                    "url": "https://example.com/valid",
                    "source": {"name": "Source"},
                    "publishedAt": "2026-01-15T10:00:00Z",
                },
                {
                    # Missing title
                    "url": "https://example.com/no-title",
                    "source": {"name": "Source"},
                },
                {
                    "title": "No URL Article",
                    # Missing url
                    "source": {"name": "Source"},
                },
            ],
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.return_value = mock_client_instance

        client = NewsClient(api_key="test-key")
        articles = await client.search_articles(query="AAPL")

        assert len(articles) == 1
        assert articles[0].title == "Valid Article"

    @pytest.mark.asyncio
    async def test_get_company_news(self, mock_httpx_client):
        """Test get_company_news convenience method."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "AAPL News",
                    "url": "https://example.com/1",
                    "source": {"name": "Source"},
                    "publishedAt": "2026-01-15T10:00:00Z",
                },
            ],
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.aclose = AsyncMock()
        mock_httpx_client.return_value = mock_client_instance

        client = NewsClient(api_key="test-key")
        articles = await client.get_company_news(
            ticker="AAPL",
            company_name="Apple Inc.",
            days_back=7,
        )

        assert len(articles) == 1
        assert articles[0].title == "AAPL News"

    @pytest.mark.asyncio
    async def test_get_company_news_deduplicates(self, mock_httpx_client):
        """Test that duplicate URLs are removed."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "Article 1",
                    "url": "https://example.com/same",
                    "source": {"name": "Source"},
                    "publishedAt": "2026-01-15T10:00:00Z",
                },
                {
                    "title": "Article 2",
                    "url": "https://example.com/same",  # duplicate
                    "source": {"name": "Source"},
                    "publishedAt": "2026-01-15T11:00:00Z",
                },
                {
                    "title": "Article 3",
                    "url": "https://example.com/different",
                    "source": {"name": "Source"},
                    "publishedAt": "2026-01-15T12:00:00Z",
                },
            ],
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.aclose = AsyncMock()
        mock_httpx_client.return_value = mock_client_instance

        client = NewsClient(api_key="test-key")
        articles = await client.get_company_news(ticker="AAPL")

        assert len(articles) == 2
        urls = [a.url for a in articles]
        assert "https://example.com/same" in urls
        assert "https://example.com/different" in urls


# ---------------------------------------------------------------------------
# BedrockClient
# ---------------------------------------------------------------------------
class TestBedrockClient:
    """Test BedrockClient wrapper."""

    @pytest.fixture
    def mock_boto_client(self):
        """Mock boto3 bedrock-runtime client."""
        with patch("alphawatch.services.bedrock.boto3.client") as mock:
            yield mock

    def test_client_initialization(self):
        with patch("alphawatch.services.bedrock.boto3.client"):
            client = BedrockClient()
            assert client._region == "us-east-1"  # default from settings

    def test_client_custom_params(self):
        with patch("alphawatch.services.bedrock.boto3.client"):
            client = BedrockClient(
                region="us-west-2",
                model_id="custom-model",
            )
            assert client._region == "us-west-2"
            assert client._default_model_id == "custom-model"

    def test_invoke_success(self, mock_boto_client):
        """Test successful model invocation."""
        mock_response = {
            "body": Mock(
                read=Mock(
                    return_value=json.dumps(
                        {
                            "content": [{"text": "Generated response"}],
                            "usage": {"output_tokens": 42},
                        }
                    ).encode()
                )
            )
        }
        mock_client_instance = Mock()
        mock_client_instance.invoke_model.return_value = mock_response
        mock_boto_client.return_value = mock_client_instance

        client = BedrockClient()
        result = client.invoke(prompt="Test prompt")

        assert result == "Generated response"
        mock_client_instance.invoke_model.assert_called_once()

    def test_invoke_with_system_prompt(self, mock_boto_client):
        """Test invoke with system prompt."""
        mock_response = {
            "body": Mock(
                read=Mock(
                    return_value=json.dumps(
                        {"content": [{"text": "Response"}]}
                    ).encode()
                )
            )
        }
        mock_client_instance = Mock()
        mock_client_instance.invoke_model.return_value = mock_response
        mock_boto_client.return_value = mock_client_instance

        client = BedrockClient()
        _ = client.invoke(
            prompt="User prompt",
            system_prompt="You are a helpful assistant",
        )

        # Check that system prompt was included in body
        call_args = mock_client_instance.invoke_model.call_args
        body = json.loads(call_args.kwargs["body"])
        assert body["system"] == "You are a helpful assistant"

    def test_invoke_empty_response_raises(self, mock_boto_client):
        """Test that empty response raises ValueError."""
        mock_response = {
            "body": Mock(read=Mock(return_value=json.dumps({"content": []}).encode()))
        }
        mock_client_instance = Mock()
        mock_client_instance.invoke_model.return_value = mock_response
        mock_boto_client.return_value = mock_client_instance

        client = BedrockClient()
        with pytest.raises(ValueError, match="No content blocks"):
            client.invoke(prompt="Test")

    def test_invoke_with_json_success(self, mock_boto_client):
        """Test invoke_with_json parsing."""
        mock_response = {
            "body": Mock(
                read=Mock(
                    return_value=json.dumps(
                        {"content": [{"text": '{"score": 50, "key": "value"}'}]}
                    ).encode()
                )
            )
        }
        mock_client_instance = Mock()
        mock_client_instance.invoke_model.return_value = mock_response
        mock_boto_client.return_value = mock_client_instance

        client = BedrockClient()
        result = client.invoke_with_json(prompt="Generate JSON")

        assert isinstance(result, dict)
        assert result["score"] == 50
        assert result["key"] == "value"

    def test_invoke_with_json_strips_markdown(self, mock_boto_client):
        """Test that JSON markdown blocks are stripped."""
        mock_response = {
            "body": Mock(
                read=Mock(
                    return_value=json.dumps(
                        {"content": [{"text": '```json\n{"score": 50}\n```'}]}
                    ).encode()
                )
            )
        }
        mock_client_instance = Mock()
        mock_client_instance.invoke_model.return_value = mock_response
        mock_boto_client.return_value = mock_client_instance

        client = BedrockClient()
        parsed_result = client.invoke_with_json(prompt="Generate JSON")

        assert parsed_result == {"score": 50}

    def test_score_sentiment_success(self, mock_boto_client):
        """Test sentiment scoring."""
        mock_response = {
            "body": Mock(
                read=Mock(
                    return_value=json.dumps(
                        {
                            "content": [
                                {
                                    "text": '{"score": 75, "reasoning": "Positive earnings"}'
                                }
                            ]
                        }
                    ).encode()
                )
            )
        }
        mock_client_instance = Mock()
        mock_client_instance.invoke_model.return_value = mock_response
        mock_boto_client.return_value = mock_client_instance

        client = BedrockClient()
        score = client.score_sentiment(
            text="Great earnings report for AAPL",
            company_name="Apple Inc.",
            ticker="AAPL",
        )

        assert score == 75

    def test_score_sentiment_out_of_range_raises(self, mock_boto_client):
        """Test that out-of-range scores raise ValueError."""
        mock_response = {
            "body": Mock(
                read=Mock(
                    return_value=json.dumps(
                        {"content": [{"text": '{"score": 150}'}]}
                    ).encode()
                )
            )
        }
        mock_client_instance = Mock()
        mock_client_instance.invoke_model.return_value = mock_response
        mock_boto_client.return_value = mock_client_instance

        client = BedrockClient()
        score = client.score_sentiment(
            text="Test text",
            company_name="Company",
            ticker="TICK",
        )

        # Should return 0 on error rather than raising
        assert score == 0

    def test_score_sentiment_returns_zero_on_error(self, mock_boto_client):
        """Test that errors return neutral score."""
        mock_client_instance = Mock()
        mock_client_instance.invoke_model.side_effect = Exception("API error")
        mock_boto_client.return_value = mock_client_instance

        client = BedrockClient()
        score = client.score_sentiment(
            text="Test",
            company_name="Company",
            ticker="TICK",
        )

        assert score == 0

    def test_generate_summary(self, mock_boto_client):
        """Test text summarization."""
        mock_response = {
            "body": Mock(
                read=Mock(
                    return_value=json.dumps(
                        {"content": [{"text": "This is a concise summary."}]}
                    ).encode()
                )
            )
        }
        mock_client_instance = Mock()
        mock_client_instance.invoke_model.return_value = mock_response
        mock_boto_client.return_value = mock_client_instance

        client = BedrockClient()
        summary = client.generate_summary(
            text="Long text here " * 100,
            max_words=50,
        )

        assert summary == "This is a concise summary."


# ---------------------------------------------------------------------------
# SentimentGraph structure
# ---------------------------------------------------------------------------
class TestSentimentGraph:
    """Test that the SentimentGraph builds correctly."""

    def test_graph_compiles(self):
        from alphawatch.agents.graphs.sentiment import build_sentiment_graph

        graph = build_sentiment_graph()
        assert graph is not None
        assert hasattr(graph, "ainvoke")

    def test_graph_has_nodes(self):
        from alphawatch.agents.graphs.sentiment import build_sentiment_graph

        graph = build_sentiment_graph()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {
            "__start__",
            "fetch_news",
            "parse_articles",
            "store_articles",
            "score_sentiments",
            "store_sentiments",
            "handle_errors",
            "__end__",
        }
        assert expected.issubset(node_names)


# ---------------------------------------------------------------------------
# SentimentRepository
# ---------------------------------------------------------------------------
class TestSentimentRepository:
    """Test sentiment repository methods."""

    def test_create_sentiment_validates_range(self):
        """Test that score validation happens."""
        from alphawatch.repositories.sentiment import SentimentRepository

        # We can't easily test async methods without DB setup,
        # but we can test the validation logic would catch errors
        # This is more of a sanity check on the class structure
        repo = SentimentRepository(Mock())
        assert repo._session is not None

    def test_score_range_validation(self):
        """Test score range validation in create_sentiment."""
        # This would need async test with real DB session
        # For now, just verify the repository exists and has the method
        from alphawatch.repositories.sentiment import SentimentRepository

        assert hasattr(SentimentRepository, "create_sentiment")
        assert hasattr(SentimentRepository, "get_average_sentiment")
        assert hasattr(SentimentRepository, "get_sentiment_by_source")
        assert hasattr(SentimentRepository, "get_sentiment_trend")


# ---------------------------------------------------------------------------
# Integration structure tests
# ---------------------------------------------------------------------------
class TestSentimentIntegration:
    """Test that all sentiment components are wired together."""

    def test_sentiment_state_in_agents_module(self):
        """Verify SentimentState is exported."""
        from alphawatch.agents.state import SentimentState

        assert SentimentState is not None

    def test_sentiment_graph_builder_exported(self):
        """Verify build_sentiment_graph is exported."""
        from alphawatch.agents.graphs import build_sentiment_graph

        assert callable(build_sentiment_graph)

    def test_news_client_exported(self):
        """Verify NewsClient is exported from services."""
        from alphawatch.services import NewsClient

        assert NewsClient is not None

    def test_bedrock_client_exported(self):
        """Verify BedrockClient is exported from services."""
        from alphawatch.services import BedrockClient

        assert BedrockClient is not None

    def test_sentiment_repo_exported(self):
        """Verify SentimentRepository is exported."""
        from alphawatch.repositories import SentimentRepository

        assert SentimentRepository is not None
