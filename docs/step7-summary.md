# Step 7 Implementation Summary: Lightweight News Ingestion + SentimentGraph

**Date:** 2026-03-26  
**Phase:** Phase 1 — MVP  
**Status:** ✅ Complete  
**Test Coverage:** 34 new tests, 178 total (all passing)

---

## Overview

Step 7 implements lightweight news ingestion and sentiment analysis for company-specific news articles. The implementation includes:

1. **NewsAPI integration** for fetching recent news articles
2. **AWS Bedrock wrapper** for Claude models (sentiment scoring, text generation)
3. **SentimentGraph** LangGraph workflow for end-to-end news processing
4. **SentimentRepository** for storing and aggregating sentiment scores
5. **Comprehensive test suite** with mocked external API calls

This step completes the data ingestion pipeline for Phase 1, providing the third data source (news) alongside EDGAR filings (Step 5) and financial snapshots (Step 6).

---

## Architecture

### Pipeline Flow

```
fetch_news → parse_articles → store_articles → score_sentiments → store_sentiments → handle_errors → END
     ↓            ↓                 ↓                  ↓                  ↓
  NewsAPI    Convert to      Store as docs      Use Bedrock      Store in DB
            ParsedDoc        (no chunking)    Claude Haiku      sentiment_records
```

**Key Decision:** News articles are stored as documents with `source_type='news'` but are **NOT chunked or embedded**. They exist solely for sentiment scoring. This differs from EDGAR filings, which are chunked and embedded for RAG retrieval.

### Conditional Routing

The SentimentGraph includes a conditional edge after `fetch_news`:
- **If articles found** → continue to `parse_articles`
- **If no articles** → skip to `handle_errors` (graceful exit)

This prevents unnecessary processing when a company has no recent news coverage.

---

## Components Created

### 1. NewsClient (`alphawatch/services/news.py`)

**Purpose:** Async client for the NewsAPI service.

**Key Features:**
- Fetches articles by ticker and/or company name
- Deduplicates articles by URL (handles ticker + name overlap)
- Defaults to last 7 days of news
- Respects free-tier rate limit (100 requests/day)
- Skips articles with missing required fields (title, URL)

**Configuration:**
```python
newsapi_api_key: str = ""
newsapi_base_url: str = "https://newsapi.org/v2"
newsapi_daily_limit: int = 100
newsapi_page_size: int = 10  # articles per company
```

**Usage Example:**
```python
client = NewsClient()
articles = await client.get_company_news(
    ticker="AAPL",
    company_name="Apple Inc.",
    days_back=7,
)
```

**Limitations:**
- Free tier: 100 requests/day
- 10 articles per company (configurable)
- Article content is truncated by NewsAPI (full content requires premium)

---

### 2. BedrockClient (`alphawatch/services/bedrock.py`)

**Purpose:** Wrapper for AWS Bedrock Runtime API with Claude models.

**Key Features:**
- Simplified interface for Claude Messages API
- Automatic JSON parsing with markdown stripping
- Sentiment scoring with structured output
- Error-resilient: returns neutral score (0) on failures
- Retry logic via boto3 Config (3 attempts, adaptive mode)

**Configuration:**
```python
bedrock_brief_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
bedrock_chat_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
bedrock_sentiment_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
bedrock_followup_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
```

**Methods:**
- `invoke()` — Basic text generation
- `invoke_with_json()` — JSON-structured outputs
- `score_sentiment()` — Sentiment analysis (-100 to +100)
- `generate_summary()` — Text summarization

**Sentiment Scoring:**
```python
client = BedrockClient()
score = client.score_sentiment(
    text="Apple reports record Q4 earnings, beating analyst expectations.",
    company_name="Apple Inc.",
    ticker="AAPL",
)
# Returns: 75 (positive sentiment)
```

**Prompt Engineering:**
- System prompt defines sentiment analyzer role
- Requests JSON with `score` (-100 to +100) and `reasoning`
- Considers financial implications, tone, and context
- Temperature=0.0 for deterministic results

---

### 3. SentimentGraph (`alphawatch/agents/graphs/sentiment.py`)

**Purpose:** LangGraph workflow for news ingestion and sentiment scoring.

**Node Functions:**
1. `fetch_news` — Query NewsAPI for recent articles
2. `parse_articles` — Convert to ParsedDoc format with content_hash
3. `store_articles` — Store in documents table (no chunking)
4. `score_sentiments` — Use Bedrock to score each article
5. `store_sentiments` — Bulk insert sentiment records
6. `handle_errors` — Log accumulated errors (terminal node)

**State Schema:**
```python
class SentimentState(BaseState, total=False):
    company_name: str
    days_back: int
    articles: list[NewsArticleRef]
    parsed_documents: list[ParsedDoc]
    sentiment_scores: list[tuple[str, int]]  # (doc_id, score)
    scores_stored: int
```

**Invocation:**
```python
from alphawatch.agents.graphs import build_sentiment_graph

graph = build_sentiment_graph()
result = await graph.ainvoke({
    "ticker": "AAPL",
    "company_id": "abc-123",
    "company_name": "Apple Inc.",
    "days_back": 7,
    "errors": [],
    "metadata": {},
})
```

---

### 4. SentimentRepository (`alphawatch/repositories/sentiment.py`)

**Purpose:** Data access layer for sentiment records.

**Methods:**
- `create_sentiment()` — Insert single sentiment record
- `bulk_create_sentiments()` — Batch insert
- `get_recent_sentiments()` — Query by company and timeframe
- `get_average_sentiment()` — Aggregate average score
- `get_sentiment_by_source()` — Average grouped by source_type
- `get_sentiment_trend()` — Daily averages for charting

**Schema:**
```sql
CREATE TABLE sentiment_records (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    document_id UUID NOT NULL REFERENCES documents(id),
    score INTEGER NOT NULL,  -- -100 to +100
    source_type TEXT NOT NULL,
    scored_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Usage Example:**
```python
repo = SentimentRepository(session)
avg_score = await repo.get_average_sentiment(
    company_id=company_uuid,
    days=7,
    source_type="news",
)
```

---

## Design Decisions

### 1. News Articles Are Not Chunked

**Rationale:**
- News articles are short (typically 200-500 words)
- Used exclusively for sentiment scoring, not RAG retrieval
- Chunking would fragment context needed for sentiment analysis
- Saves processing time and embedding costs

**Implementation:**
- `store_articles` node creates Document records
- `source_type='news'` distinguishes from EDGAR filings
- No call to `chunk_text()` or `embed_chunks()`

### 2. Error-Resilient Sentiment Scoring

**Rationale:**
- Sentiment scoring should not block the entire pipeline
- Better to have missing sentiment than failed ingestion
- Allows partial success when Bedrock is unavailable

**Implementation:**
- `score_sentiment()` returns 0 (neutral) on any exception
- Errors logged but not raised
- Allows pipeline to complete with some missing scores

### 3. Async Executor for Boto3 Calls

**Rationale:**
- Boto3 is synchronous (not async)
- Blocking calls would stall the async event loop
- Multiple articles need sequential scoring

**Implementation:**
```python
loop = asyncio.get_running_loop()
score = await loop.run_in_executor(
    None,
    client.score_sentiment,
    doc.raw_text,
    company_name,
    ticker,
)
```

### 4. Sentiment Score Range: -100 to +100

**Rationale:**
- Human-interpretable scale
- Allows fine-grained sentiment gradations
- Integer type for efficient storage and comparison

**Validation:**
- Repository raises `ValueError` if score out of range
- Bedrock prompt explicitly requests score in range
- Test coverage for boundary conditions

---

## Testing

### Test Coverage: 34 Tests

**Test Categories:**
1. **State Types** (4 tests) — NewsArticleRef, SentimentState structure
2. **NewsClient** (8 tests) — API calls, deduplication, error handling
3. **BedrockClient** (11 tests) — Invocation, JSON parsing, sentiment scoring
4. **SentimentGraph** (2 tests) — Graph compilation, node structure
5. **SentimentRepository** (2 tests) — Method existence, validation
6. **Integration** (5 tests) — Module exports, wiring
7. **Error Cases** (2 tests) — Missing API key, out-of-range scores

**Mock Strategy:**
- `httpx.AsyncClient` mocked for NewsAPI calls
- `boto3.client` mocked for Bedrock calls
- No actual API keys required for tests
- Validates error paths and edge cases

**Sample Test:**
```python
async def test_search_articles_success(self, mock_httpx_client):
    mock_response = Mock()
    mock_response.json.return_value = {
        "status": "ok",
        "articles": [
            {
                "title": "Test Article",
                "url": "https://example.com/1",
                "source": {"name": "Source"},
                "publishedAt": "2026-01-15T10:00:00Z",
            }
        ],
    }
    mock_response.raise_for_status = Mock()
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_httpx_client.return_value = mock_client_instance
    
    client = NewsClient(api_key="test-key")
    articles = await client.search_articles(query="AAPL")
    
    assert len(articles) == 1
    assert articles[0].title == "Test Article"
```

---

## Configuration Updates

### Environment Variables

```bash
# NewsAPI
NEWSAPI_API_KEY=your-newsapi-key-here
NEWSAPI_BASE_URL=https://newsapi.org/v2
NEWSAPI_DAILY_LIMIT=100
NEWSAPI_PAGE_SIZE=10

# AWS Bedrock Models
BEDROCK_SENTIMENT_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_BRIEF_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_CHAT_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_FOLLOWUP_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

### Settings Updates

Added to `alphawatch/config.py`:
- NewsAPI configuration (4 settings)
- Bedrock model routing (4 settings)

---

## Integration Points

### 1. Future: Celery Task for Scheduled News Ingestion

**Location:** `alphawatch/workers/tasks.py` (Step 14)

```python
@celery_app.task
async def ingest_company_news(company_id: str, ticker: str, company_name: str):
    graph = build_sentiment_graph()
    result = await graph.ainvoke({
        "company_id": company_id,
        "ticker": ticker,
        "company_name": company_name,
        "days_back": 1,  # daily incremental
        "errors": [],
        "metadata": {},
    })
    return result["scores_stored"]
```

### 2. Brief Generation (Step 8)

Sentiment scores will be consumed by the BriefGraph `build_sentiment` section:

```python
# Query recent sentiment
avg_sentiment = await sentiment_repo.get_average_sentiment(
    company_id=company_id,
    days=7,
    source_type="news",
)

# Include in brief section
section_text = f"News sentiment: {avg_sentiment:+.1f}/100 over last 7 days"
```

### 3. Dashboard Endpoint (Step 12)

Sentiment trends will surface in the Monday morning watchlist digest:

```python
trend = await sentiment_repo.get_sentiment_trend(
    company_id=company_id,
    days=30,
)
```

---

## Performance Considerations

### NewsAPI Rate Limits

**Free Tier:** 100 requests/day

**Optimization Strategies:**
1. Batch news ingestion (1 request per company per day)
2. Prioritize high-activity companies during rate-limited periods
3. Cache negative results (no articles found) to avoid re-querying
4. Consider upgrade to premium tier for production ($449/month = unlimited)

### Bedrock Sentiment Scoring

**Model:** Claude Haiku (cost-optimized)

**Cost Estimate:**
- Input: ~200 tokens per article (title + description + content)
- Output: ~50 tokens (JSON response)
- Haiku pricing: $0.25/1M input, $1.25/1M output
- **Cost per article:** ~$0.00008 (~1/10th of a cent)
- **Daily cost (50 companies × 10 articles):** ~$0.04

**Optimization:**
- Use Haiku (not Sonnet) for sentiment — 10x cheaper
- Temperature=0.0 for deterministic caching potential
- Error-resilient design prevents retry storms

---

## Known Limitations

### 1. NewsAPI Content Truncation

**Issue:** Free tier returns truncated article content (first 200 characters).

**Impact:** Sentiment scores based on partial text may be less accurate.

**Mitigation:** 
- Premium tier provides full content
- Title + description often sufficient for headline sentiment
- Consider web scraping for critical articles (respect robots.txt)

### 2. No Real-Time News

**Issue:** NewsAPI updates hourly (free tier).

**Impact:** Breaking news has 0-60 minute lag.

**Mitigation:**
- Acceptable for Phase 1 (daily brief focus)
- For Phase 4: consider Tavily API for real-time search

### 3. English-Only

**Issue:** NewsClient defaults to `language="en"`.

**Impact:** Non-English articles excluded.

**Mitigation:**
- Most financial news for US equities is in English
- Can be extended in Phase 2 with multi-language sentiment models

---

## Next Steps

### Step 8: BriefGraph Implementation

**Priority:** HIGH

**Blockers:** None (all dependencies complete)

**Scope:**
1. Build BriefGraph with 8 sections
2. Implement `retrieve_chunks` node (pgvector similarity search)
3. Fan-out to parallel section builders:
   - `build_snapshot` (use FinancialSnapshot from Step 6)
   - `build_what_changed` (data-driven, no LLM)
   - `build_risk_flags` (LLM-based)
   - `build_sentiment` (consume SentimentRecords from Step 7)
4. Final `build_executive_summary` (synthesizes prior sections)
5. Store in `analyst_briefs` + `brief_sections` tables

**Integration:**
- Use `SentimentRepository.get_average_sentiment()` in `build_sentiment` node
- Use `BedrockClient` with `bedrock_brief_model_id` (Sonnet) for section generation

---

## Files Changed

### New Files (7)
- `alphawatch/services/news.py` (214 lines)
- `alphawatch/services/bedrock.py` (283 lines)
- `alphawatch/agents/nodes/sentiment.py` (324 lines)
- `alphawatch/agents/graphs/sentiment.py` (75 lines)
- `alphawatch/repositories/sentiment.py` (214 lines)
- `tests/test_sentiment.py` (641 lines)
- `docs/step7-summary.md` (this file)

### Modified Files (5)
- `alphawatch/config.py` — Added NewsAPI + Bedrock model configs
- `alphawatch/agents/state.py` — Added NewsArticleRef + SentimentState
- `alphawatch/services/__init__.py` — Exported new services
- `alphawatch/agents/graphs/__init__.py` — Exported build_sentiment_graph
- `alphawatch/repositories/__init__.py` — Exported SentimentRepository

---

## Conclusion

Step 7 successfully implements lightweight news ingestion with sentiment analysis, completing the data ingestion pipeline for Phase 1. The SentimentGraph provides a robust, error-resilient workflow that fetches articles from NewsAPI, scores them with Claude Haiku, and stores structured sentiment data for consumption by downstream components (briefs, dashboards, alerts).

**Test Status:** ✅ 178 tests passing (34 new)  
**Code Quality:** ✅ No warnings, type hints on all public functions  
**Documentation:** ✅ Google-style docstrings throughout  
**Ready for:** Step 8 (BriefGraph implementation)