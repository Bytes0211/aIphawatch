# AIphaWatch — Project Status

**Version:** 1.0  
**Last Updated:** 2026-03-26 (updated after Steps 9 & 10)  
**Lifecycle:** Phase 1 (MVP) underway — Agent layer complete  
**Overall Status:** ✅ Phase 0 complete; 🔧 Phase 1 MVP in progress (Steps 1–10 of 14 complete)
**Deliverables Completed:** Product requirements document; full technical specification; LangGraph workflow designs (IngestionGraph, BriefGraph, ChatGraph, SentimentGraph); PostgreSQL schema with pgvector and RLS; FastAPI API contracts; React component tree; Celery job definitions; Terraform module layout; CI/CD pipeline spec; **Terraform infrastructure — 8 modules + staging/production environments**; **Database schema — 12 ORM models + Alembic migration + HNSW index + RLS policies**; **FastAPI skeleton — auth middleware, tenant context, health endpoint**; **Company resolution + Watchlist CRUD — repositories, schemas, routers**; **EDGAR ingestion — IngestionGraph + EDGAR client + chunker + embeddings service**; **Financial API — Alpha Vantage client + snapshot repository + upsert**; **News ingestion — NewsAPI client + BedrockClient + SentimentGraph + sentiment repository**; **BriefGraph — 8-section analyst brief with parallel fan-out, pgvector RAG retrieval, BriefRepository, ChunkRepository**; **ChatGraph — multi-turn RAG chat with SSE streaming, chunk cache, rolling context summary, ChatRepository**; **Test suite — 360 tests passing**

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
9. ~~**Brief API endpoint**~~ ✅ Complete (implemented as part of Step 8/10)
10. ~~**ChatGraph + SSE streaming endpoint**~~ ✅ Complete
11. **React `ChatContainer` + streaming UI** ← **next**

---

## Progress Snapshot

| Phase | Scope | Status | Notes |
|-------|-------|--------|-------|
| Phase 0 — Planning & Alignment | PRD, technical specification, architectural direction | ✅ Complete | All planning documents authored; 14-step Phase 1 build order defined |
| Phase 1 — MVP | Auth, watchlist, EDGAR ingestion, financial API, news, analyst briefs, chat, dashboard, infra | 🔧 In Progress | Steps 1–10 complete; full agent layer done; React UI is next |
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
- [x] Step 9: Brief API endpoint — `GET/POST /api/companies/{id}/brief`, `BriefSectionResponse`, `BriefGenerateResponse` (implemented alongside Step 8)
- [x] Step 10: `ChatGraph` + SSE streaming endpoint — multi-turn RAG chat, chunk cache, rolling context summary, ChatRepository, 5 SSE event types (360 tests)
- [ ] Step 11: React `ChatContainer` + streaming UI
- [ ] Step 12: Dashboard endpoint + React `WatchlistGrid`
- [ ] Step 13: `PeersChips` + competitor detection in chat
- [ ] Step 14: CI/CD pipeline + staging deployment

Steps 1–4 can be parallelized; Steps 5–10 are sequential; Steps 11–13 can be parallelized once APIs exist.

---

## Step 10 Implementation Details — ChatGraph + SSE Streaming

**Completed:** 2026-03-26
**Test Coverage:** 95 new tests (360 total)
**Files Created:** 6 (`agents/nodes/chat.py`, `agents/graphs/chat.py`, `repositories/chat.py`, `schemas/chat.py`, `api/routers/chat.py`, `tests/test_chat.py`)
**Files Modified:** 5 (`agents/state.py`, `agents/graphs/__init__.py`, `repositories/__init__.py`, `api/main.py`, `README.md`)

### Components

1. **ChatGraph** (`agents/graphs/chat.py`) — LangGraph workflow with conditional routing
   - Pipeline: `prepare_context → detect_intent → check_chunk_cache | retrieve_chunks → generate_response → generate_followups → persist_turn → maybe_summarize → handle_errors`
   - Two conditional edges: intent-based routing (rag/comparison → cache, general → response) and cache-hit routing (hit → response, miss → retrieval)
   - 9 nodes total; compiled with `StateGraph(ChatState)`

2. **ChatGraph nodes** (`agents/nodes/chat.py`) — 9 node functions
   - `prepare_context` — loads session from DB; builds LLM context window (rolling summary + last 10 raw messages)
   - `detect_intent` — Claude Haiku classifies query as 'rag', 'comparison', or 'general'; extracts comparison ticker; falls back to 'rag' on error
   - `check_chunk_cache` — loads previously retrieved chunks by UUID from session cache; sets `cache_hit` flag
   - `retrieve_chunks` — embeds user query via Titan Embeddings v2; pgvector cosine search; merges with cached chunks; tracks `new_chunk_ids`
   - `generate_response` — Claude Sonnet with context window + source chunks + user question; builds citations
   - `generate_followups` — Claude Haiku generates 3 follow-up chips; caps at 3; graceful fallback
   - `persist_turn` — appends user + assistant messages to `ChatSession.messages`; updates chunk cache via `ChatRepository`
   - `maybe_summarize` — triggers at >20 messages; summarises `messages[summary_through..N-10]` via Claude Haiku; persists rolling summary
   - `handle_errors` — terminal node; logs accumulated errors

3. **ChatRepository** (`repositories/chat.py`) — session CRUD and turn persistence
   - `create_session()`, `get_session()`, `get_sessions_for_user_company()`
   - `append_messages()` — reassigns `messages` list for SQLAlchemy dirty-tracking on `ARRAY(JSONB)`
   - `update_chunk_cache()` — deduplicates before merging new chunk IDs
   - `update_context_summary()` — stores rolling summary text and `summary_through` index
   - `get_messages()`, `delete_session()` (ownership-enforced)

4. **Chat schemas** (`schemas/chat.py`) — Pydantic request/response models
   - Session: `ChatSessionCreateRequest`, `ChatSessionResponse`, `ChatSessionListResponse`
   - Messages: `SendMessageRequest`, `MessageHistoryResponse`, `MessageSchema`
   - SSE events: `SSETokenEvent`, `SSECitationsEvent`, `SSEFollowupsEvent`, `SSEDoneEvent`, `SSEErrorEvent`

5. **Chat router** (`api/routers/chat.py`) — 6 endpoints
   - `POST /api/chat/sessions` — create session (201)
   - `GET /api/chat/sessions?company_id=...` — list sessions
   - `GET /api/chat/sessions/{id}` — get session (ownership-enforced)
   - `DELETE /api/chat/sessions/{id}` — delete session (204, ownership-enforced)
   - `GET /api/chat/sessions/{id}/messages` — full message history
   - `POST /api/chat/sessions/{id}/messages` — **SSE streaming** response

6. **New state types** (`agents/state.py`)
   - `Citation` — chunk_id, document_id, title, source_type, source_url, excerpt
   - `ChatMessage` — role (user/assistant/system), content, citations, turn_index, created_at
   - `ChatState` — extends `BaseState`; session_id, messages, context_summary, chunk cache, intent, response, citations, followups

### Key Design Decisions

- **SSE simulation from complete Bedrock response:** Bedrock's `invoke()` returns the complete text. Sentences are split on `[.!?]` boundaries and emitted as individual `token` events so the UI sees progressive rendering without requiring native token streaming (which would need Bedrock's `invoke_model_with_response_stream`).
- **Chunk cache → >70% hit target:** `check_chunk_cache` loads all previously retrieved chunks from the session. For follow-up questions in the same session, no re-embedding is needed. Only truly new chunk IDs are merged into the cache via `persist_turn`.
- **Rolling context summary at 20 messages:** `maybe_summarize` triggers when `len(messages) + 2 > SUMMARY_THRESHOLD (20)`. Summarises `messages[summary_through..N-10]` using Claude Haiku, leaving the last 10 messages as verbatim context. Total LLM input stays ~4,200 tokens regardless of session length.
- **Intent detection falls back to 'rag':** On any Bedrock error, `detect_intent` returns `intent='rag'` rather than `'general'`. This ensures we always attempt retrieval rather than answering blindly without sources.
- **Ownership enforced at every session endpoint:** All session reads, writes, and deletes check `session.user_id == user.user_id` before proceeding. Returns 404 (not 403) to avoid leaking session existence.
- **ARRAY(JSONB) mutation requires reassignment:** PostgreSQL `ARRAY(JSONB)` columns must be reassigned (not mutated in-place) for SQLAlchemy to mark them dirty. `append_messages` always creates a new list.

### SSE Event Sequence

`POST /api/chat/sessions/{session_id}/messages` — response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`

```
# Happy path — one token event per sentence, then metadata, then done:
data: {"type": "token",     "token": "Apple's revenue grew..."}
data: {"type": "token",     "token": "...12% year-over-year. "}
data: {"type": "citations", "citations": [
         {"chunk_id": "<uuid>", "document_id": "<uuid>",
          "title": "Apple 10-K 2025", "source_type": "edgar_10k",
          "source_url": "https://...", "excerpt": "Revenue grew 12%..."}
       ]}
data: {"type": "followups", "questions": [
         "What drove the revenue growth?",
         "How do margins compare year-over-year?",
         "What is the capex outlook for FY2026?"
       ]}
data: {"type": "done",      "session_id": "<uuid>"}

# On error (graph failure or unhandled exception):
data: {"type": "error",     "message": "An unexpected error occurred. Please try again."}
```

**Event type reference:**

| Event type | When emitted | Key fields |
|---|---|---|
| `token` | Once per sentence fragment during response | `token: str` |
| `citations` | After all token events, before followups | `citations: list[CitationSchema]` |
| `followups` | After citations, only if questions were generated | `questions: list[str]` |
| `done` | Always last on success | `session_id: str` |
| `error` | On graph failure or unhandled exception | `message: str` |

### Integration Points

- **React ChatContainer (Step 11):** Consumes SSE stream via `useSSE.ts`; dispatches `token` events to Zustand `chatStore` for progressive rendering; fires `citations` and `followups` events on stream close.
- **Dashboard (Step 12):** `ChatRepository.get_sessions_for_user_company()` surfaces session count per watchlist entry.
- **Celery (Step 14):** `build_chat_graph()` is ready for async task dispatch; no scheduler integration needed (chat is user-triggered).

---

## Step 9 Implementation Details — Brief API Endpoints + Schemas

**Completed:** 2026-03-26
**Test Coverage:** 13 new tests (265 total at time of step completion)
**Files Created:** 2 (`schemas/brief.py`, `tests/test_briefs_api.py`)
**Files Modified:** 2 (`api/routers/briefs.py`, `api/main.py`)

### Components

1. **Brief schemas** (`schemas/brief.py`) — Pydantic request/response models
   - `BriefSectionResponse` — id, section_type, section_order, content (JSONB), created_at
   - `BriefResponse` — full brief with eager-loaded sections list (defaults to `[]`)
   - `BriefSummaryResponse` — lightweight metadata-only view for listing
   - `BriefGenerateRequest` — optional `query_text` to seed chunk retrieval
   - `BriefGenerateResponse` — status (`"completed"` | `"completed_with_errors"`), brief_id, company_id, ticker, message

2. **Brief router** (`api/routers/briefs.py`) — 4 endpoints
   - `GET /api/companies/{company_id}/brief` — returns latest brief with all sections, or `null` if none generated yet
   - `POST /api/companies/{company_id}/brief/generate` — runs `BriefGraph.ainvoke()` inline; returns `BriefGenerateResponse`
   - `GET /api/companies/{company_id}/brief/{brief_id}/sections` — sections for a specific brief (ownership-checked)
   - `GET /api/companies/{company_id}/briefs` — recent brief summaries, no sections loaded

### Key Design Decisions

- **`GET .../brief` returns `null`, not 404, when no brief exists** — allows the React UI to detect first-time state and prompt the user to generate.
- **`BriefGenerateResponse.status` is `"completed_with_errors"` when partial** — caller can display sections that succeeded while surfacing the degraded state.
- **Ownership check on section fetch** — verifies `brief.user_id == user.user_id` AND `brief.company_id == company_id`; returns 404 on mismatch (no 403, to avoid leaking brief existence).
- **`BriefGraph.ainvoke()` runs inline** — synchronous for Phase 1; will be dispatched to a Celery task in Step 14 to avoid blocking the request.

### Integration Points

- **BriefGraph (Step 8):** ✅ `BriefGraph.ainvoke()` stores the brief via `BriefRepository`; the API layer reads it back via `get_brief_by_id()` with `selectinload(sections)`
- **Chat (Step 10):** ✅ Brief sections' `suggested_followups` content is available to the chat UI as initial follow-up chips before the first message is sent
- **Dashboard (Step 12):** `BriefRepository.list_for_user_company()` powers the per-company brief history view

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

- **Brief API (Step 9):** ✅ `build_brief_graph().ainvoke(BriefState(...))` returns `brief_id`; `GET /api/companies/{id}/brief` fetches via `BriefRepository.get_brief_by_id()`
- **Chat (Step 10):** ✅ `ChunkRepository.get_chunks_by_ids()` hydrates the chat chunk cache from `retrieved_chunk_ids` stored in `ChatSession`; `BriefRepository.get_latest_for_user_company()` surfaces the most recent brief per watchlist entry in the dashboard
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

## Risks & Mitigations

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

- `docs/PRD-AIphaWatch-2026-03-25.md` — Product requirements document
- `docs/AIphaWatch-TechnicalSpec.md` — Full technical specification
- `docs/step7-summary.md` — Step 7 detailed implementation notes (SentimentGraph)
- `developer/developer-journal.md` — Running log of all step completions
- `AGENTS.md` — AI agent guidance, graph shapes, SSE event reference, API endpoint table
- `README.md` — Project overview, architecture diagrams, getting started
