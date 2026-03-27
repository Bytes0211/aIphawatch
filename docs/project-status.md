# AIphaWatch — Project Status

**Version:** 1.0  
**Last Updated:** 2026-03-26  
**Lifecycle:** Phase 1 (MVP) underway — Data ingestion complete  
**Overall Status:** ✅ Phase 0 complete; 🔧 Phase 1 MVP in progress (Steps 1–9 of 14 complete)
**Deliverables Completed:** Product requirements document; full technical specification; LangGraph workflow designs (IngestionGraph, BriefGraph, ChatGraph, SentimentGraph); PostgreSQL schema with pgvector and RLS; FastAPI API contracts; React component tree; Celery job definitions; Terraform module layout; CI/CD pipeline spec; **Terraform infrastructure — 8 modules + staging/production environments**; **Database schema — 12 ORM models + Alembic migration + HNSW index + RLS policies**; **FastAPI skeleton — auth middleware, tenant context, health endpoint**; **Company resolution + Watchlist CRUD — repositories, schemas, routers**; **EDGAR ingestion — IngestionGraph + EDGAR client + chunker + embeddings service**; **Financial API — Alpha Vantage client + snapshot repository + upsert**; **News ingestion — NewsAPI client + BedrockClient + SentimentGraph + sentiment repository**; **BriefGraph — 8-section analyst brief with parallel fan-out, pgvector RAG retrieval, BriefRepository, ChunkRepository**; **Brief API — 4 endpoints (get latest, generate, sections, list)**; **Test suite — 265 tests passing**

---

## Executive Summary

AIphaWatch gives buy-side analysts a single dashboard that answers: "What changed across my companies, and what does it mean?" Every Monday morning, Sarah opens the platform, sees a prioritized digest of her 12 watched companies — new SEC filings, price moves, sentiment shifts, risk flags — and drills into any company for a structured analyst brief with citations she can trust enough to act on. When the brief raises questions, she switches to a conversational chat interface grounded in the same source data to dig deeper.

The platform reduces per-company research time from hours to minutes, delivers citation-backed briefs where every claim links to a real source, and provides a professional-grade chat experience that remembers context across follow-up questions. Phase 1 (MVP) is underway — the goal is a demo-ready product where Sarah can watch companies, read briefs, and chat with the data.

---

## Current Focus

1. ~~**Terraform infrastructure scaffolding** — VPC, RDS, ElastiCache, Cognito, ECS, S3, CloudFront, Secrets Manager~~ ✅ Complete
2. ~~**Database schema deployment** — all 12 tables, HNSW vector index, RLS policies~~ ✅ Complete
3. ~~**FastAPI skeleton** — Cognito JWT middleware, tenant context injection, health endpoint~~ ✅ Complete
4. ~~**Company resolution + Watchlist CRUD endpoints**~~ ✅ Complete
5. ~~**EDGAR ingestion service + IngestionGraph**~~ ✅ Complete
6. ~~**Financial API ingestion + FinancialSnapshot storage**~~ ✅ Complete
7. ~~**Lightweight news ingestion + SentimentGraph**~~ ✅ Complete
8. ~~**BriefGraph — all 8 sections with parallel fan-out**~~ ✅ Complete
9. ~~**Brief API endpoint + React `BriefViewer`**~~ ✅ Complete
10. **`ChatGraph` + SSE streaming endpoint** ← **next**

---

## Progress Snapshot

| Phase | Scope | Status | Notes |
|-------|-------|--------|-------|
| Phase 0 — Planning & Alignment | PRD, technical specification, architectural direction | ✅ Complete | All planning documents authored; 14-step Phase 1 build order defined |
| Phase 1 — MVP | Auth, watchlist, EDGAR ingestion, financial API, news, analyst briefs, chat, dashboard, infra | 🔧 In Progress | Steps 1–9 complete; ChatGraph + SSE streaming is next |
| Phase 2 — Intelligence Expansion | Full news depth, sentiment enrichment, risk flag detection, document upload, competitor lookup | ⏳ Planned | — |
| Phase 3 — SaaS Hardening | Tenant branding, alert notifications, admin panel, bulk import, brief export, usage tracking | ⏳ Planned | — |
| Phase 4 — Scale & Polish | Earnings transcripts, watchlist sharing, scheduled briefs, comparison views, audit log, API access | ⏳ Planned | — |

---

## Phase 1 — MVP Task Tracking

**Goal:** Sarah can watch 12 companies, see what changed, read analyst briefs, and chat with the data. Demo-ready.

- [x] Step 1: Terraform — VPC, RDS, Redis, Cognito, ECS, S3, CloudFront, Secrets (8 modules + staging/production)
- [x] Step 2: Database schema — 12 ORM models, Alembic migration, HNSW index, RLS policies, 67 tests
- [x] Step 3: FastAPI skeleton — Cognito JWT auth, TenantMiddleware, tenant-scoped DB sessions, health endpoint
- [x] Step 4: Company resolution + Watchlist CRUD — repositories, schemas, routers (88 tests)
- [x] Step 5: EDGAR ingestion — IngestionGraph, EDGAR client, chunker, embeddings, admin trigger (113 tests)
- [x] Step 6: Financial API — Alpha Vantage client, snapshot repository, upsert, safe parsing (142 tests)
- [x] Step 7: Lightweight news ingestion + `SentimentGraph` — NewsAPI client, BedrockClient, sentiment repository (178 tests)
- [x] Step 8: `BriefGraph` — all 8 sections with parallel fan-out, pgvector RAG retrieval, BriefRepository, ChunkRepository (249 tests)
- [x] Step 9: Brief API — 4 endpoints (get latest, generate, sections, list), schemas (265 tests)
- [ ] Step 10: `ChatGraph` + SSE streaming endpoint
- [ ] Step 11: React `ChatContainer` + streaming UI
- [ ] Step 12: Dashboard endpoint + React `WatchlistGrid`
- [ ] Step 13: `PeersChips` + competitor detection in chat
- [ ] Step 14: CI/CD pipeline + staging deployment

Steps 1–4 can be parallelized; Steps 5–8 are sequential; Steps 9–13 can be parallelized once APIs exist.

---

## Step 8 Implementation Details — BriefGraph

**Completed:** 2026-03-26
**Test Coverage:** 71 new tests (249 total)
**Files Created:** 5 (`agents/nodes/brief.py`, `agents/graphs/brief.py`, `repositories/briefs.py`, `repositories/chunks.py`, `tests/test_brief.py`)
**Files Modified:** 4 (`agents/state.py`, `agents/graphs/__init__.py`, `repositories/__init__.py`, `README.md`)

### Components

1. **BriefGraph** (`agents/graphs/brief.py`) — LangGraph workflow with fan-out/fan-in
   - Entry: `retrieve_chunks` (pgvector similarity search)
   - Fan-out via `Send` to 5 parallel section builders
   - Fan-in: `assemble_sections` → `build_executive_summary` → `build_suggested_followups` → `store_brief` → `handle_errors`
   - 11 nodes total; compiled with `StateGraph(BriefState)`

2. **BriefGraph nodes** (`agents/nodes/brief.py`) — 11 node functions
   - `retrieve_chunks` — embeds broad company query via Titan Embeddings v2; top-8 EDGAR chunks from pgvector HNSW index
   - `build_snapshot` — purely data-driven; reads latest `FinancialSnapshot`, no LLM
   - `build_what_changed` — diffs two most recent snapshots; 0.5% threshold; no LLM (eliminates hallucination risk)
   - `build_risk_flags` — LLM (Claude Sonnet) identifies up to 5 risk flags; sorts by severity; maps chunk indices → chunk IDs
   - `build_sentiment` — reads pre-computed `SentimentRecord` aggregates; overall + by-source + 30-day trend
   - `build_sources` — deduplicates retrieved chunks by document_id; purely data-driven
   - `assemble_sections` — fan-in node; collects all 5 parallel sections into ordered list
   - `build_executive_summary` — runs last; synthesises from assembled sections + chunks; cited chunk IDs validated against known list (hallucination guard)
   - `build_suggested_followups` — Claude Haiku generates 4 contextual follow-up questions for UI chips
   - `store_brief` — persists `AnalystBrief` + all sections via `BriefRepository.bulk_create_sections()`
   - `handle_errors` — terminal node; logs accumulated errors

3. **BriefRepository** (`repositories/briefs.py`) — data access for briefs and sections
   - `create_brief()`, `bulk_create_sections()`, `get_latest_for_user_company()`
   - `get_brief_by_id()`, `list_for_user_company()`, `get_section()` (by type)
   - `sections` eager-loaded via `selectinload` on get queries

4. **ChunkRepository** (`repositories/chunks.py`) — pgvector similarity search
   - `similarity_search()` — cosine distance (`<=>`) on HNSW index; restricted by `company_id`; optional source-type filter
   - `get_chunks_by_ids()` — bulk hydration for chat chunk cache (Step 10)
   - `count_chunks_for_company()` — pre-flight check before BriefGraph invocation

5. **New state types** (`agents/state.py`)
   - `ChunkResult` — retrieved chunk with similarity score, source metadata
   - `RiskFlagItem` — severity, category, description, source_chunk_ids
   - `BriefSectionData` — section_type, section_order, JSONB content
   - `BriefState` — extends `BaseState`; all section fields + retrieved_chunks + brief_id

### Key Design Decisions

- **Fan-out is real parallelism:** 5 section builders dispatch via `Send` after `retrieve_chunks`. LangGraph runs them concurrently; wall-clock time for the parallel phase is bounded by the slowest single node (~2s for risk_flags LLM call), not the sum.
- **Executive summary runs last:** Cannot hallucinate a fact not present in the section data passed to it. Cited chunk IDs are validated post-generation against the actual retrieved set.
- **"What Changed" is purely data-driven:** 0.5% threshold on snapshot diffs + analyst rating comparison. Zero LLM calls. Eliminates hallucination in the highest-signal brief section.
- **Sentiment consumed, not recomputed:** `build_sentiment` reads pre-scored `SentimentRecord` rows written by `SentimentGraph`. No re-scoring at brief generation time; avoids double Bedrock costs.
- **All imports at module level:** Moved from lazy function-body imports to module-level to enable clean `patch()` mocking in tests without `create=True`.
- **Graceful degradation:** Every node catches exceptions, appends to `errors`, and returns a fallback section rather than aborting the pipeline. A brief with a missing section is better than no brief.
- **`build_suggested_followups` uses Haiku:** Follow-up questions are low-stakes (UI chips); Claude Haiku is sufficient and costs ~10× less than Sonnet.

### Section Ordering

| # | Section Type | LLM? | Data Source |
|---|---|---|---|
| 1 | `snapshot` | ❌ | `FinancialSnapshot` (latest) |
| 2 | `what_changed` | ❌ | `FinancialSnapshot` diff |
| 3 | `risk_flags` | ✅ Sonnet | Retrieved EDGAR chunks |
| 4 | `sentiment` | ❌ | `SentimentRecord` aggregates |
| 5 | `sources` | ❌ | Retrieved chunks (dedup) |
| 6 | `executive_summary` | ✅ Sonnet | Sections + chunks |
| 7 | `suggested_followups` | ✅ Haiku | Summary + risk flags |

### Integration Points

- **Brief API (Step 9):** `build_brief_graph().ainvoke(BriefState(...))` returns `brief_id`; API endpoint fetches via `BriefRepository.get_brief_by_id()`
- **Chat (Step 10):** `ChunkRepository.get_chunks_by_ids()` hydrates the chat chunk cache from `retrieved_chunk_ids` stored in `ChatSession`
- **Dashboard (Step 12):** `BriefRepository.get_latest_for_user_company()` surfaces most recent brief metadata per watchlist entry

---

## Step 7 Implementation Details — News Ingestion + SentimentGraph

**Completed:** 2026-03-26  
**Test Coverage:** 34 new tests (178 total)  
**Files Created:** 7 (services/news.py, services/bedrock.py, agents/nodes/sentiment.py, agents/graphs/sentiment.py, repositories/sentiment.py, tests/test_sentiment.py, docs/step7-summary.md)

### Components

1. **NewsClient** (`services/news.py`) — NewsAPI integration
   - Fetches recent news articles by ticker and/or company name
   - Deduplicates by URL (handles ticker + name overlap)
   - Free tier: 100 requests/day, 10 articles per company
   - Defaults to last 7 days of news

2. **BedrockClient** (`services/bedrock.py`) — AWS Bedrock wrapper
   - Simplified interface for Claude Messages API
   - JSON-structured outputs with automatic markdown stripping
   - Sentiment scoring (-100 to +100) using Claude Haiku
   - Error-resilient: returns neutral score (0) on failures
   - Retry logic via boto3 Config (3 attempts, adaptive mode)

3. **SentimentGraph** (`agents/graphs/sentiment.py`) — LangGraph workflow
   - Pipeline: `fetch_news → parse_articles → store_articles → score_sentiments → store_sentiments → handle_errors`
   - Conditional routing: skips pipeline if no articles found
   - News articles stored as documents with `source_type='news'` but NOT chunked/embedded (sentiment-only)

4. **SentimentRepository** (`repositories/sentiment.py`) — Data access layer
   - `create_sentiment()`, `bulk_create_sentiments()` for storage
   - `get_average_sentiment()`, `get_sentiment_by_source()` for aggregation
   - `get_sentiment_trend()` for daily time-series data

### Key Design Decisions

- **News articles NOT chunked:** Short articles (200-500 words) used only for sentiment scoring, not RAG retrieval. Saves processing time and embedding costs.
- **Error-resilient scoring:** `score_sentiment()` returns neutral score (0) on Bedrock failures rather than blocking the pipeline.
- **Async executor for boto3:** Synchronous boto3 calls run off the event loop via `asyncio.run_in_executor()` to prevent blocking.
- **Sentiment score range (-100 to +100):** Human-interpretable scale with validation at repository layer.

### Configuration Added

```bash
# NewsAPI
NEWSAPI_API_KEY=your-key-here
NEWSAPI_PAGE_SIZE=10
NEWSAPI_DAILY_LIMIT=100

# Bedrock Models
BEDROCK_SENTIMENT_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_BRIEF_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_CHAT_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_FOLLOWUP_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

### Integration Points

- **BriefGraph (Step 8):** `build_sentiment` section will consume sentiment scores via `SentimentRepository.get_average_sentiment()`
- **Dashboard (Step 12):** Sentiment trends surface in Monday morning digest via `get_sentiment_trend()`
- **Celery (Step 14):** Scheduled news ingestion task will invoke `build_sentiment_graph().ainvoke()`

### Performance Notes

- **NewsAPI rate limits:** Free tier 100 requests/day = ~3-4 companies per day. Requires batching or upgrade to premium ($449/month unlimited) for production.
- **Bedrock cost:** Claude Haiku at ~$0.00008 per article. Daily cost for 50 companies × 10 articles = ~$0.04/day.

---

## Risks & Mitigations</text>

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM hallucination in analyst briefs | High | Medium | Citation-per-claim enforced in all prompts; post-generation validation that cited sources exist; "What changed" is data-driven (snapshot diffs, no LLM) |
| SEC EDGAR rate limits and parsing inconsistency across filers | Medium | High | Respectful crawling with exponential backoff; `content_hash` (SHA-256) deduplication to avoid re-processing; `unstructured` library for multi-format parsing |
| Free-tier financial API limits (Alpha Vantage: 25 req/day) insufficient at scale | Medium | High | Prioritize refresh by most-watched companies; display `last_updated_at` timestamps; plan migration to Polygon.io for production |
| NewsAPI free-tier rate limits (100 req/day) insufficient for multi-tenant production | Medium | High | Batch news ingestion once per day per company; prioritize high-activity watchlists; upgrade to premium tier ($449/month unlimited) for production; consider Tavily API as alternative |
| Chunk cache staleness after new document ingestion | Medium | Medium | Cache keyed by `(company_id, document_id, chunk_id)`; invalidate per-company on new document ingestion; retrieval timestamps in citations surface staleness to analysts |
| Multi-tenant data isolation leakage via vector search | High | Low | Repository-layer `tenant_id` scoping + PostgreSQL RLS as defense-in-depth; vector search filtered by `company_id` set derived from watchlist join |
| Brief generation P95 latency exceeds 15s SLA | Medium | Medium | BriefGraph fan-out runs 4 sections in parallel via LangGraph `Send`; exec summary synthesizes pre-built sections (fastest path); LangSmith tracing to identify bottlenecks |
| Chat token costs exceeding budget on long sessions | Medium | Medium | Chunk cache targets >70% hit rate per session; rolling context summary compresses messages >20 into ~300 tokens; token usage tracked per tenant in CloudWatch |

---

## Key Decisions & Dependencies

- **MIT License:** Portfolio project — commercial risk is theoretical at this stage.
- **LangGraph for all agent workflows:** Celery owns the clock (scheduled ingestion); LangGraph owns the workflow logic (graph execution and state). They meet at well-defined task → graph run boundaries.
- **"What changed" is purely data-driven:** Snapshot diffs + filing date comparison, no LLM. Eliminates hallucination risk in the highest-signal brief section.
- **Citation-per-claim enforcement:** Every claim in the executive summary must trace to a retrieved chunk. Enforced in the prompt and validated post-generation.
- **pgvector over dedicated vector DB:** Single PostgreSQL 16 instance for relational + vector data simplifies ops for Phase 1. HNSW index on `document_chunks.embedding` (1536-dim, cosine ops, `m=16`, `ef_construction=64`) for fast ANN search.
- **Chunk cache for chat cost control:** `retrieved_chunk_ids` persisted in `ChatSession`. Follow-up questions load from Redis/Postgres without re-embedding. Target >70% cache hit rate per session.
- **Rolling context summary for long sessions:** When message count >20, messages `0..N-10` are summarized into `context_summary`. LLM receives summary + last 10 raw messages + top-8 chunks (~4,200 tokens total, well within Claude's 200K context window).
- **Companies are global entities, not tenant-scoped:** AAPL is shared. Tenant isolation enforced through watchlist joins at the repository layer with RLS as defense-in-depth.
- **BriefGraph fan-out:** `build_snapshot`, `build_what_changed`, `build_risk_flags`, and `build_sentiment` run in parallel via LangGraph `Send` after `retrieve_chunks`. `build_exec_summary` runs last, synthesizing sections rather than raw data to prevent unsupported claims.
- **News articles are sentiment-only, not chunked:** NewsAPI articles stored with `source_type='news'` but excluded from vector search. Sentiment scores from Claude Haiku aggregated for brief `build_sentiment` section and dashboard trending. Keeps RAG focused on authoritative sources (SEC filings, financial data).

---

## References

- `docs/PRD-AIphaWatch-2026-03-25.md`
- `docs/AIphaWatch-TechnicalSpec.md`
- `docs/step7-summary.md`
- `developer/developer-journal.md`
- `README.md`
