# AIphaWatch — Technical Specification

**AI-Powered Equity Intelligence Platform**

| | |
|---|---|
| Author | Steven Cotton |
| Version | 1.0 |
| Date | 2026-03-25 |
| Status | Draft |
| PRD Reference | PRD-AIphaWatch-2026-03-25 |

---

## Table of Contents

1. [Overview](#1-overview)
2. [LangGraph Architecture](#2-langgraph-architecture)
3. [Database Schema](#3-database-schema)
4. [FastAPI Service Architecture](#4-fastapi-service-architecture)
5. [Key Pydantic Schemas](#5-key-pydantic-schemas)
6. [React Component Tree](#6-react-component-tree)
7. [Background Jobs (Celery)](#7-background-jobs-celery)
8. [Infrastructure (Terraform)](#8-infrastructure-terraform)
9. [Phase 1 Build Order](#9-phase-1-build-order)
10. [Observability](#10-observability)
11. [Appendix: External API Notes](#appendix-external-api-notes)

---

## 1. Overview

This document defines the technical architecture, data models, LangGraph workflows, API contracts, and React component structure for AIphaWatch — a multi-tenant SaaS platform that delivers AI-powered financial intelligence to buy-side analysts.

The system ingests data from SEC EDGAR, financial APIs, and news sources on a schedule, stores embeddings in pgvector, and uses LangGraph-orchestrated agents to generate structured analyst briefs and power a multi-turn RAG chat interface.

> **Phase 1 scope:** watchlist management, EDGAR ingestion, financial API ingestion, lightweight news sentiment, full 8-section analyst brief generation, professional-grade RAG chat, and dashboard. All Phase 1 components are covered in this spec.

### 1.1 System Context

| Layer | Technology | Role |
|---|---|---|
| Frontend | React 18 + TypeScript + shadcn/ui | Dashboard, chat UI, brief viewer |
| API Gateway | FastAPI + Uvicorn | REST + SSE endpoints, auth middleware |
| Agent Layer | LangGraph + AWS Bedrock (Claude) | Brief generation, chat RAG, ingestion workflows |
| Scheduler | Celery + Redis | Timed ingestion jobs, background tasks |
| Database | PostgreSQL (RDS) + pgvector | Relational data + vector embeddings |
| Cache | Redis | Session state, chunk cache, rate limiting |
| Storage | S3 | Uploaded documents, tenant assets |
| Auth | AWS Cognito | JWT tokens, multi-tenant org isolation |
| IaC | Terraform | Reproducible staging + production environments |
| CI/CD | GitHub Actions | Test, build, deploy pipeline |

---

## 2. LangGraph Architecture

LangGraph owns all stateful, multi-step agent workflows. Celery owns the clock. The two interact at well-defined boundaries: Celery triggers a LangGraph run by enqueuing a task with the input payload; LangGraph executes the graph and writes results to Postgres.

### 2.1 Workflows Overview

| Workflow | Trigger | LangGraph Graph | Output |
|---|---|---|---|
| Ingestion | Celery schedule / watchlist add | `IngestionGraph` | Documents + chunks in Postgres/pgvector |
| Brief Generation | User opens company page | `BriefGraph` | `BriefSection` rows in Postgres |
| Chat Turn | User sends chat message | `ChatGraph` | Streamed response + updated `ChatSession` |
| Competitor Lookup | Chat detects second entity | `CompetitorGraph` (subgraph of ChatGraph) | Ephemeral metric for current turn |
| Sentiment Scoring | Post news ingestion | `SentimentGraph` | `SentimentRecord` rows in Postgres |

### 2.2 Shared State Schema

All graphs extend a common base state:

```python
class BaseState(TypedDict):
    tenant_id: str
    user_id:   str
    company_id: str
    ticker:    str
    errors:    List[str]          # accumulated non-fatal errors
    metadata:  Dict[str, Any]     # graph-specific passthrough
```

### 2.3 IngestionGraph

#### State

```python
class IngestionState(BaseState):
    filing_types:       List[str]       # ["10-K", "10-Q", "8-K"]
    new_filings:        List[FilingRef]
    parsed_documents:   List[ParsedDoc]
    chunks:             List[Chunk]
    embeddings_stored:  int
```

#### Nodes

| Node | Input | Action | Output |
|---|---|---|---|
| `fetch_filings` | ticker, filing_types | Query EDGAR full-text search API; filter by `last_ingested_at` | `new_filings` |
| `parse_documents` | new_filings | Download filing HTML/TXT; extract sections via `unstructured`; deduplicate by `content_hash` | `parsed_documents` |
| `chunk_documents` | parsed_documents | Split into 512-token chunks with 64-token overlap; attach section metadata | `chunks` |
| `embed_chunks` | chunks | Batch embed via Amazon Titan Embeddings v2; 1536-dim vectors | embeddings ready |
| `store_chunks` | chunks + embeddings | Upsert `Document` + `DocumentChunk` rows; update `last_ingested_at` | `embeddings_stored` |
| `handle_errors` | errors[] | Log errors; emit alert if critical filing missed | terminal |

#### Edges

```
fetch_filings ──→ parse_documents    (if new_filings not empty)
fetch_filings ──→ END                (if no new filings)
parse_documents ──→ chunk_documents
chunk_documents ──→ embed_chunks
embed_chunks ──→ store_chunks
store_chunks ──→ END
Any node ──→ handle_errors           (on exception)
```

---

### 2.4 BriefGraph

#### State

```python
class BriefState(BaseState):
    session_id:          str
    prior_brief_id:      Optional[str]      # for delta calculation
    financial_snapshot:  FinancialSnapshot
    recent_filings:      List[FilingRef]
    news_articles:       List[NewsArticle]
    retrieved_chunks:    List[Chunk]
    sections:            Dict[SectionType, Any]   # built incrementally
    brief_id:            str
```

#### Nodes

| Node | Action | Writes to `sections` |
|---|---|---|
| `load_context` | Fetch latest `FinancialSnapshot`, recent `Documents`, prior `BriefSection` rows for delta | — |
| `build_header` | Populate company, ticker, sector, `generated_at`, `session_id` | `header` |
| `build_snapshot` | Map `FinancialSnapshot` fields + aggregate sentiment score to snapshot bar schema | `snapshot` |
| `build_what_changed` | Diff current vs prior snapshot + new filings/news since prior brief. **Data-driven, no LLM.** | `what_changed` |
| `retrieve_chunks` | Semantic search over `DocumentChunks` for top-20 relevant chunks | — |
| `build_risk_flags` | Keyword scan + Bedrock Claude classification on retrieved chunks for covenant/litigation/guidance/insider signals | `risk_flags` |
| `build_sentiment` | Aggregate `SentimentRecords`; compute weighted score + delta vs prior period | `sentiment` |
| `build_exec_summary` | Bedrock Claude synthesis over sections 2–5 + retrieved chunks. Enforces citation-per-claim in prompt. | `executive_summary` |
| `build_sources` | Collect all cited document URLs + timestamps from sections | `sources` |
| `build_followups` | Bedrock Claude generates 3 follow-up questions from brief content | `suggested_followups` |
| `persist_brief` | Write `AnalystBrief` + `BriefSection` rows to Postgres in a single transaction | — |

#### Key Design Decisions

- `build_what_changed` is purely data-driven (snapshot diffs + filing date comparison). No LLM involved. This eliminates hallucination risk in the highest-signal section.
- `build_exec_summary` runs last — it synthesizes all prior sections, not raw source data, ensuring it cannot claim something not already surfaced elsewhere in the brief.
- **Fan-out pattern:** `build_snapshot`, `build_what_changed`, `build_risk_flags`, and `build_sentiment` run in parallel via LangGraph's `Send` API after `retrieve_chunks` completes.
- Each section node writes independently to `state["sections"]`. `persist_brief` reads all sections and writes in a single transaction.

#### Edges

```
load_context ──→ retrieve_chunks
retrieve_chunks ──→ [build_snapshot, build_what_changed,
                     build_risk_flags, build_sentiment]  (parallel Send)
[all four] ──→ build_exec_summary
build_exec_summary ──→ build_sources ──→ build_followups ──→ persist_brief ──→ END
```

---

### 2.5 ChatGraph

#### State

```python
class ChatState(BaseState):
    session_id:             str
    messages:               List[Message]         # full history
    context_summary:        Optional[str]         # rolling summary of messages 0..N
    summary_through:        int                   # index of last summarized message
    retrieved_chunk_ids:    List[str]             # chunk cache
    retrieved_chunks:       List[Chunk]           # populated this turn
    comparison_entity:      Optional[str]         # detected ticker for competitor lookup
    llm_context:            List[Message]         # what actually goes to Bedrock
    response:               str                   # streamed response
    citations:              List[Citation]
    suggested_followups:    List[str]
```

#### Nodes

| Node | Action |
|---|---|
| `prepare_context` | Build `llm_context`: `context_summary` + last 10 raw messages. Triggers summarization if message count > 20. |
| `detect_intent` | Classify user message: single-company RAG, comparison query, or general. Extract `comparison_entity` if present. |
| `check_chunk_cache` | For chunks already in `retrieved_chunk_ids`, load from Redis/Postgres without re-embedding the query. |
| `retrieve_chunks` | Semantic search for chunks NOT in cache. Merge with cached chunks. Update `retrieved_chunk_ids` in session. |
| `competitor_lookup` | Subgraph: parallel fetch of specific metric for `comparison_entity` from financial API. Session-scoped, not persisted. |
| `generate_response` | Bedrock Claude (`claude-3-5-sonnet`) with `llm_context` + `retrieved_chunks`. Stream via SSE. Inject citations inline. |
| `generate_followups` | Bedrock Claude generates 3 follow-up chips from response content. |
| `persist_turn` | Append user message + assistant response to `ChatSession.messages`. Update `retrieved_chunk_ids`. |
| `summarize_context` | Background node: if message count > 20, summarize messages 0..N-10 into `context_summary`. Updates `summary_through`. |

#### Conditional Edges

```
detect_intent ──→ check_chunk_cache     (single-company or comparison)
detect_intent ──→ generate_response     (general question, no retrieval needed)
check_chunk_cache ──→ retrieve_chunks   (cache miss or partial hit)
check_chunk_cache ──→ generate_response (full cache hit)
retrieve_chunks ──→ competitor_lookup   (if comparison_entity detected)
retrieve_chunks ──→ generate_response   (no comparison)
competitor_lookup ──→ generate_response
generate_response ──→ generate_followups ──→ persist_turn ──→ END
persist_turn ──→ summarize_context      (async, if threshold crossed)
```

> **Token budget per Bedrock call:** `context_summary` (~300 tokens) + last 10 messages (~1,500 tokens) + top-8 retrieved chunks (~2,000 tokens) + system prompt (~400 tokens) = ~4,200 tokens input. Well within `claude-3-5-sonnet`'s 200K context window.

---

## 3. Database Schema

Full PostgreSQL schema with indexes and Row-Level Security policies.

### 3.1 Core Tables

```sql
CREATE TABLE tenants (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  slug        TEXT UNIQUE NOT NULL,         -- used for subdomain routing
  branding    JSONB NOT NULL DEFAULT '{}',  -- logo_url, primary_color, accent_color
  config      JSONB NOT NULL DEFAULT '{}',  -- watchlist_limit, thresholds, schedule
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  cognito_sub   TEXT UNIQUE NOT NULL,
  email         TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('admin', 'analyst', 'viewer')),
  preferences   JSONB NOT NULL DEFAULT '{}',
  last_login_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, email)
);
CREATE INDEX idx_users_tenant ON users(tenant_id);

CREATE TABLE companies (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker      TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  sector      TEXT,
  cik         TEXT,           -- SEC EDGAR identifier
  metadata    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_companies_ticker ON companies(ticker);
CREATE INDEX idx_companies_cik    ON companies(cik);

CREATE TABLE watchlist (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  company_id        UUID NOT NULL REFERENCES companies(id),
  alert_thresholds  JSONB NOT NULL DEFAULT '{}',
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, company_id)
);
CREATE INDEX idx_watchlist_user    ON watchlist(user_id);
CREATE INDEX idx_watchlist_company ON watchlist(company_id);
```

### 3.2 Ingestion Tables

```sql
CREATE TABLE documents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID NOT NULL REFERENCES companies(id),
  source_type   TEXT NOT NULL CHECK (source_type IN
                  ('edgar_10k','edgar_10q','edgar_8k','news','upload')),
  source_url    TEXT,
  title         TEXT NOT NULL,
  content_hash  TEXT NOT NULL,    -- SHA-256, for deduplication
  raw_text      TEXT,
  metadata      JSONB NOT NULL DEFAULT '{}',
  ingested_at   TIMESTAMPTZ DEFAULT NOW(),
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(company_id, content_hash)
);
CREATE INDEX idx_documents_company      ON documents(company_id);
CREATE INDEX idx_documents_source_type  ON documents(company_id, source_type);
CREATE INDEX idx_documents_ingested     ON documents(ingested_at DESC);

CREATE TABLE document_chunks (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  company_id    UUID NOT NULL REFERENCES companies(id),
  chunk_index   INTEGER NOT NULL,
  content       TEXT NOT NULL,
  embedding     vector(1536),     -- Amazon Titan Embeddings v2
  metadata      JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(document_id, chunk_index)
);
CREATE INDEX idx_chunks_company  ON document_chunks(company_id);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);

-- HNSW index for fast ANN search (pgvector 0.5+)
CREATE INDEX idx_chunks_embedding ON document_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

### 3.3 Financial & Sentiment Tables

```sql
CREATE TABLE financial_snapshots (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id        UUID NOT NULL REFERENCES companies(id),
  snapshot_date     DATE NOT NULL,
  price             NUMERIC(18,4),
  price_change_pct  NUMERIC(8,4),
  market_cap        BIGINT,
  pe_ratio          NUMERIC(10,2),
  debt_to_equity    NUMERIC(10,4),
  analyst_rating    TEXT,
  raw_data          JSONB NOT NULL DEFAULT '{}',
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(company_id, snapshot_date)
);
CREATE INDEX idx_snapshots_company ON financial_snapshots(company_id, snapshot_date DESC);

CREATE TABLE sentiment_records (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID NOT NULL REFERENCES companies(id),
  document_id   UUID NOT NULL REFERENCES documents(id),
  score         INTEGER NOT NULL CHECK (score BETWEEN -100 AND 100),
  source_type   TEXT NOT NULL,
  scored_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sentiment_company ON sentiment_records(company_id, scored_at DESC);
```

### 3.4 Brief Tables

```sql
CREATE TABLE analyst_briefs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id),
  company_id    UUID NOT NULL REFERENCES companies(id),
  session_id    UUID NOT NULL,
  generated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_briefs_user_company ON analyst_briefs(user_id, company_id, generated_at DESC);

CREATE TABLE brief_sections (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brief_id      UUID NOT NULL REFERENCES analyst_briefs(id) ON DELETE CASCADE,
  section_type  TEXT NOT NULL CHECK (section_type IN (
                  'header','snapshot','what_changed','risk_flags',
                  'sentiment','executive_summary','sources','suggested_followups')),
  section_order INTEGER NOT NULL,
  content       JSONB NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(brief_id, section_type)
);
CREATE INDEX idx_brief_sections_brief ON brief_sections(brief_id, section_order);
```

### 3.5 Chat & Risk Tables

```sql
CREATE TABLE chat_sessions (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 UUID NOT NULL REFERENCES users(id),
  company_id              UUID NOT NULL REFERENCES companies(id),
  active_company_ticker   TEXT NOT NULL,
  messages                JSONB[] NOT NULL DEFAULT '{}',
  context_summary         TEXT,
  context_summary_through INTEGER DEFAULT 0,
  retrieved_chunk_ids     UUID[] NOT NULL DEFAULT '{}',
  created_at              TIMESTAMPTZ DEFAULT NOW(),
  updated_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sessions_user_company ON chat_sessions(user_id, company_id, updated_at DESC);

CREATE TABLE risk_flags (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID NOT NULL REFERENCES companies(id),
  document_id   UUID REFERENCES documents(id),
  flag_type     TEXT NOT NULL CHECK (flag_type IN (
                  'covenant','litigation','guidance_cut',
                  'insider_sell','schema_drift')),
  severity      TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
  description   TEXT NOT NULL,
  detected_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_risk_flags_company ON risk_flags(company_id, detected_at DESC);
```

### 3.6 Row-Level Security

RLS is defense-in-depth. The application layer enforces tenant scoping at the repository layer; RLS catches any query that bypasses it.

```sql
ALTER TABLE users           ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist       ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyst_briefs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions   ENABLE ROW LEVEL SECURITY;

-- Example: users table policy
CREATE POLICY tenant_isolation ON users
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- Application sets tenant context on every connection:
SET LOCAL app.tenant_id = '<tenant-uuid>';
```

> **Note:** `companies` and `document_chunks` are NOT tenant-isolated at the RLS level — AAPL is a shared global entity. Tenant isolation for these is enforced through the watchlist join: the application only queries chunks for `company_id`s present in the user's watchlist.

---

## 4. FastAPI Service Architecture

### 4.1 Project Structure

```
alphawatch/
  api/
    routers/
      auth.py           # Cognito token validation, user context
      watchlist.py      # CRUD for watchlist
      companies.py      # Company resolution, metadata
      briefs.py         # Brief generation + retrieval
      chat.py           # Chat turns (SSE streaming)
      ingestion.py      # Manual ingestion triggers (admin)
      dashboard.py      # Watchlist digest endpoint
    dependencies.py     # get_current_user, get_db, get_redis
    middleware.py       # Tenant context injection
    main.py             # App factory, router registration
  agents/
    graphs/
      ingestion.py      # IngestionGraph definition
      brief.py          # BriefGraph definition
      chat.py           # ChatGraph definition
      sentiment.py      # SentimentGraph definition
    nodes/              # Individual node functions
    state.py            # TypedDict state schemas
  services/
    edgar.py            # SEC EDGAR API client
    financial.py        # Alpha Vantage / Polygon client
    news.py             # NewsAPI / Tavily client
    bedrock.py          # AWS Bedrock wrapper
    embeddings.py       # Titan Embeddings client
  repositories/
    base.py             # Tenant-scoped base repo
    companies.py
    watchlist.py
    briefs.py
    chat.py
    chunks.py           # Vector search
  workers/
    tasks.py            # Celery task definitions
    schedules.py        # Beat schedules
  models/               # SQLAlchemy ORM models
  schemas/              # Pydantic request/response schemas
```

### 4.2 Key API Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/api/dashboard` | Watchlist digest, sorted by most changed | analyst |
| `GET` | `/api/watchlist` | List user watchlist with latest snapshots | analyst |
| `POST` | `/api/watchlist` | Add company by ticker or name | analyst |
| `DELETE` | `/api/watchlist/{company_id}` | Remove from watchlist | analyst |
| `GET` | `/api/companies/resolve?q={query}` | Resolve ticker/name to canonical company | analyst |
| `GET` | `/api/companies/{company_id}/brief` | Get latest brief or trigger generation | analyst |
| `POST` | `/api/companies/{company_id}/brief/generate` | Force regenerate brief | analyst |
| `GET` | `/api/companies/{company_id}/brief/{brief_id}/sections` | Get all sections for a brief | analyst |
| `GET` | `/api/chat/sessions?company_id={id}` | List chat sessions for a company | analyst |
| `POST` | `/api/chat/sessions` | Create new chat session | analyst |
| `POST` | `/api/chat/sessions/{session_id}/messages` | Send message — returns SSE stream | analyst |
| `GET` | `/api/chat/sessions/{session_id}/messages` | Get full message history | analyst |
| `POST` | `/api/ingestion/trigger` | Manually trigger ingestion for a company | admin |
| `GET` | `/api/ingestion/status/{company_id}` | Get ingestion status + `last_ingested_at` | analyst |

### 4.3 Tenant Middleware

Every request carries a JWT from Cognito. The middleware extracts `tenant_id` from the token and sets it on the database connection for RLS.

```python
class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token  = extract_bearer(request)
        claims = verify_cognito_jwt(token)
        request.state.tenant_id = claims["custom:tenant_id"]
        request.state.user_id   = claims["sub"]
        request.state.role      = claims["custom:role"]
        async with db_session() as session:
            await session.execute(
                text("SET LOCAL app.tenant_id = :tid"),
                {"tid": request.state.tenant_id}
            )
        return await call_next(request)
```

### 4.4 SSE Streaming (Chat)

Chat responses stream token-by-token from Bedrock via Server-Sent Events. The final event carries citations and suggested follow-ups.

```python
# Event stream format:
data: {"type": "token",     "content": "Apple's"}
data: {"type": "token",     "content": " revenue"}
data: {"type": "citation",  "ref": "[10-K §MD&A]", "url": "https://..."}
data: {"type": "followups", "items": ["What drove...", "Compare to..."]}
data: {"type": "done"}

# FastAPI endpoint:
@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest,
                       user=Depends(get_current_user)):
    async def event_generator():
        async for event in chat_graph.astream(state):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_generator(),
                             media_type="text/event-stream")
```

---

## 5. Key Pydantic Schemas

### 5.1 Dashboard Response

```python
class CompanyCard(BaseModel):
    company_id:              str
    ticker:                  str
    name:                    str
    sector:                  str
    price:                   float
    price_change_pct:        float
    sentiment_score:         Optional[int]   # -100 to +100
    sentiment_delta:         Optional[int]   # vs prior period
    new_filings_count:       int
    risk_flag_count:         int
    risk_flag_max_severity:  Optional[str]
    last_updated_at:         datetime
    brief_id:                Optional[str]   # latest brief ID

class DashboardResponse(BaseModel):
    cards:      List[CompanyCard]   # sorted by change_score desc
    as_of:      datetime
    time_range: str                 # "since_last_login" | "24h" | "7d"
```

### 5.2 Brief Section Content Schemas

Each `brief_sections.content` JSONB column follows a defined schema per `section_type`:

```json
// snapshot
{
  "price": 182.45,
  "price_change_pct": 2.3,
  "market_cap": 2850000000000,
  "pe_ratio": 28.4,
  "debt_to_equity": 1.73,
  "analyst_rating": "Buy",
  "sentiment_score": 42,
  "as_of": "2026-03-25T09:00:00Z"
}

// what_changed
{
  "changes": [
    {
      "type": "filing",
      "description": "New 10-Q filed 2026-03-20",
      "url": "https://www.sec.gov/...",
      "severity": "medium"
    },
    {
      "type": "price",
      "description": "+12.3% since last session",
      "severity": "high"
    }
  ]
}

// risk_flags
{
  "flags": [
    {
      "flag_type": "litigation",
      "severity": "high",
      "description": "Class action mentioned in 10-Q §Legal Proceedings",
      "source": "[10-Q §Legal, 2026-03-20]"
    }
  ]
}

// executive_summary
{
  "summary": "Apple reported strong Q1 results [10-Q §MD&A, 2026-03-20]...",
  "citations": [
    {
      "ref": "[10-Q §MD&A, 2026-03-20]",
      "url": "https://www.sec.gov/..."
    }
  ]
}
```

---

## 6. React Component Tree

### 6.1 Application Structure

```
src/
  app/
    layout.tsx                    # Root layout: nav, auth guard, tenant theme
    dashboard/page.tsx            # Monday morning watchlist digest
    company/[id]/
      page.tsx                    # Company overview: brief + chat
      brief/page.tsx              # Full brief view
      chat/page.tsx               # Chat interface
  components/
    dashboard/
      WatchlistGrid.tsx           # Grid of CompanyCards
      CompanyCard.tsx             # Per-company summary card
      TimeRangeSelector.tsx       # "Since last login / 24h / 7d"
      AddCompanyModal.tsx         # Ticker/name search + add to watchlist
    brief/
      BriefViewer.tsx             # Full 8-section brief renderer
      SnapshotBar.tsx             # Metrics row: price, P/E, sentiment, etc.
      WhatChanged.tsx             # Delta bullets with severity badges
      RiskFlags.tsx               # Flag cards with severity color coding
      SentimentScore.tsx          # Score + delta + source breakdown
      ExecutiveSummary.tsx        # Prose with inline citation links
      SourcesList.tsx             # Cited sources with timestamps
      FollowUpChips.tsx           # 3 clickable chips → seeds chat
    chat/
      ChatContainer.tsx           # Session state, message list, input
      MessageList.tsx             # Scrollable message thread
      MessageBubble.tsx           # User / assistant / system message styles
      InlineCitation.tsx          # Clickable [source] reference
      FollowUpChips.tsx           # Post-response suggested prompts
      CompanyContextBanner.tsx    # Persistent "Active: AAPL" header
      StreamingIndicator.tsx      # Typing dots during generation
      NewSessionButton.tsx        # Clears session state
    shared/
      SentimentBadge.tsx          # Green/yellow/red -100..+100 display
      SeverityBadge.tsx           # low/medium/high/critical color pill
      SkeletonBrief.tsx           # Loading state for brief generation
      PeersChips.tsx              # 3-4 peer tickers → pre-seed comparison chat
  hooks/
    useWatchlist.ts               # TanStack Query: watchlist CRUD
    useBrief.ts                   # TanStack Query: brief fetch + poll
    useChatSession.ts             # Zustand: session state + SSE connection
    useSSE.ts                     # Generic SSE hook with reconnect
    useTenantTheme.ts             # Inject CSS vars from tenant branding
  stores/
    chatStore.ts                  # Zustand: messages, session_id, chunk cache state
    uiStore.ts                    # Zustand: sidebar state, active company
  lib/
    api.ts                        # Typed API client (fetch wrappers)
    auth.ts                       # Cognito SDK setup
    sse.ts                        # SSE event parser + dispatcher
```

### 6.2 Key Component Contracts

```typescript
// CompanyCard
interface CompanyCardProps {
  card:      CompanyCard
  onSelect:  (companyId: string) => void
  onAddPeer: (ticker: string) => void
}

// ChatContainer
interface ChatContainerProps {
  companyId:  string
  sessionId:  string | null    // null = create new session
  seedPrompt: string | null    // from FollowUpChips or PeersChips
}

// MessageBubble
interface MessageBubbleProps {
  role:        "user" | "assistant" | "system"
  content:     string
  citations:   Citation[]
  followUps:   string[]
  isStreaming: boolean
}
```

### 6.3 State Management Strategy

| State Type | Tool | Rationale |
|---|---|---|
| Server data (briefs, watchlist, snapshots) | TanStack Query | Caching, background refetch, stale-while-revalidate |
| Chat session (messages, SSE state) | Zustand | Low-latency streaming updates without React re-render overhead |
| UI state (sidebar, active company) | Zustand | Lightweight, no boilerplate |
| Auth (user, tenant, role) | React Context | Read-only after login, infrequently changes |
| Tenant theme (CSS vars) | CSS custom properties | Applied once at layout level, no JS state needed |

---

## 7. Background Jobs (Celery)

Celery workers run alongside the FastAPI container in the same ECS service definition (separate task definition for workers). Redis serves as both the Celery broker and result backend.

### 7.1 Scheduled Tasks

| Task | Schedule | Action |
|---|---|---|
| `ingest_edgar_filings` | Every hour (market hours: 9am–5pm ET weekdays) | For each watched company: run `IngestionGraph` if new filings detected on EDGAR |
| `refresh_financial_snapshots` | Every hour (market hours), daily otherwise | Pull latest price/metrics from Alpha Vantage or Polygon for all watched companies |
| `ingest_news_sentiment` | Every 4 hours | Pull recent news via NewsAPI/Tavily; run `SentimentGraph` for new articles |
| `cleanup_stale_sessions` | Daily at 2am ET | Archive `ChatSession`s inactive > 30 days; compact messages arrays |
| `watchlist_change_detection` | After every ingestion run | Compute `change_score` per company; cache in Redis for dashboard sort |

### 7.2 Change Score Calculation

The dashboard sorts companies by `change_score` — a composite signal of how much has happened since the user's last session. Cached in Redis per `(user_id, company_id)`.

```python
change_score = (
    new_filing_count        * 30   # filings carry highest weight
  + risk_flag_count         * 25   # new risk flags
  + abs(price_change_pct)   *  2   # price movement
  + abs(sentiment_delta)    *  1   # sentiment shift
)
```

> `change_score` is intentionally simple. The goal is directional sorting, not precise ranking. Weights are tenant-configurable in Phase 3.

---

## 8. Infrastructure (Terraform)

### 8.1 AWS Resource Map

| Resource | Service | Notes |
|---|---|---|
| API container | ECS Fargate | 2 vCPU / 4GB, auto-scaling 1–10 tasks |
| Worker container | ECS Fargate | 1 vCPU / 2GB, auto-scaling 1–5 tasks |
| Frontend | S3 + CloudFront | Static React build, global CDN |
| Database | RDS PostgreSQL 16 | db.t3.medium, Multi-AZ in production, pgvector extension |
| Cache / Broker | ElastiCache Redis 7 | cache.t3.micro, cluster mode for production |
| File storage | S3 | Tenant-prefixed buckets for uploaded docs |
| Secrets | AWS Secrets Manager | All API keys, DB credentials |
| Auth | Cognito User Pool | Per-tenant org isolation via custom attributes |
| LLM | Bedrock (`claude-3-5-sonnet`) | On-demand, cross-region inference enabled |
| Embeddings | Bedrock (Titan Embeddings v2) | Batch for ingestion, single for query |
| DNS / SSL | Route 53 + ACM | Wildcard cert for tenant subdomains |
| Monitoring | CloudWatch + X-Ray | Logs, metrics; LangSmith for LLM tracing |

### 8.2 Terraform Module Structure

```
infra/
  modules/
    vpc/          # VPC, subnets, security groups
    rds/          # PostgreSQL with pgvector
    elasticache/  # Redis cluster
    ecs/          # API + worker task definitions
    s3/           # Document storage buckets
    cognito/      # User pool + app clients
    cloudfront/   # Frontend CDN distribution
    secrets/      # Secrets Manager entries
  environments/
    staging/      # main.tf, variables.tf, terraform.tfvars
    production/   # main.tf, variables.tf, terraform.tfvars
```

### 8.3 CI/CD Pipeline (GitHub Actions)

| Stage | Trigger | Steps |
|---|---|---|
| Test | Every PR | `pytest` (backend), `jest` (frontend), `mypy` type check, `ruff` lint |
| Build | Merge to main | Docker build API + worker images; `npm build` frontend; push to ECR + S3 |
| Deploy Staging | Merge to main | `terraform apply` (staging); ECS rolling update; smoke tests |
| Deploy Production | Manual tag `v*` | `terraform apply` (production); ECS blue/green deploy; health check |

---

## 9. Phase 1 Build Order

The recommended build sequence minimises rework by establishing shared infrastructure before feature layers. Each step produces a testable, demonstrable artifact.

| Step | What to Build | Demo-able Output |
|---|---|---|
| 1 | Terraform: VPC, RDS, Redis, Cognito, ECS skeletons | Infrastructure boots cleanly in staging |
| 2 | Database schema: all tables, indexes, RLS policies | `psql` connects; schema validates |
| 3 | FastAPI skeleton: auth middleware, tenant context, health endpoint | `POST /auth` returns JWT; `tenant_id` injected |
| 4 | Company resolution + Watchlist CRUD endpoints | Add AAPL to watchlist; persists across sessions |
| 5 | EDGAR ingestion service + `IngestionGraph` | AAPL 10-K chunks appear in `document_chunks` |
| 6 | Financial API ingestion + `FinancialSnapshot` storage | Snapshot bar populates with real AAPL data |
| 7 | Lightweight news ingestion + `SentimentGraph` | Sentiment score appears for AAPL |
| 8 | `BriefGraph`: all 8 sections | Full analyst brief generates for AAPL in < 15s |
| 9 | Brief API endpoint + React `BriefViewer` | Browser renders a complete styled brief |
| 10 | `ChatGraph` + SSE streaming endpoint | Chat responds to "What are the key risks?" with citations |
| 11 | React `ChatContainer` + streaming UI | Tokens stream word-by-word; citations are clickable |
| 12 | Dashboard endpoint + React `WatchlistGrid` | Monday morning view renders with `change_score` sort |
| 13 | `PeersChips` + on-demand competitor detection in chat | "Compare AAPL to MSFT" works in chat |
| 14 | CI/CD pipeline + staging deployment | Full demo environment live at staging URL |

> **Parallelisation note:** Steps 1–4 are infrastructure and can be parallelised with a second engineer. Steps 5–8 are the core data pipeline and must be sequential. Steps 9–12 are the UI layer and can be parallelised against step 13 once the APIs exist.

---

## 10. Observability

### 10.1 LangSmith Tracing

Every LangGraph run is traced in LangSmith. Key metrics to monitor per graph:

| Graph | Key Metrics |
|---|---|
| `IngestionGraph` | Chunks per document, embedding latency, `content_hash` collision rate (dedup efficiency) |
| `BriefGraph` | Sections generated, token usage per section, citation count in exec summary, total latency |
| `ChatGraph` | Cache hit rate, retrieval count, token usage, response latency, followup generation quality |
| `SentimentGraph` | Score distribution, articles scored per run, latency per article |

### 10.2 Application Metrics (CloudWatch)

- Brief generation P50/P95 latency (target: < 15s P95)
- Chat response P50/P95 latency (target: < 5s cache hit, < 15s retrieval)
- Chunk cache hit rate per session (target: > 70%)
- EDGAR ingestion lag: new filing detected → chunks stored (target: < 1 hour)
- Bedrock token usage per tenant (for future billing)
- API error rate by endpoint

---

## Appendix: External API Notes

### SEC EDGAR

- Full-text search: `https://efts.sec.gov/LATEST/search-index?q={ticker}&dateRange=custom&startdt={date}`
- Rate limit: 10 requests/second. Set `User-Agent` header to identify your app (required by SEC policy).
- Filing index: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}`
- Use `content_hash` (SHA-256 of `raw_text`) to avoid re-processing filings already in the database.

### Alpha Vantage (Free Tier)

- 25 API requests/day on free tier. Prioritise refresh by companies with most recent watchlist activity.
- `GLOBAL_QUOTE` endpoint for price data. `OVERVIEW` endpoint for P/E, debt/equity, analyst rating.
- For production: upgrade to premium or switch to Polygon.io (unlimited with paid plan).

### NewsAPI

- Free tier: 100 requests/day. Sufficient for Phase 1 with a small watchlist.
- Use `/v2/everything?q={ticker}&sortBy=publishedAt&pageSize=10` for recent headlines.
- For production: consider Tavily (already used in DealFinder) for better financial news coverage.

### AWS Bedrock Models

| Use Case | Model |
|---|---|
| Brief generation + chat | `claude-3-5-sonnet-20241022` |
| Sentiment scoring | `claude-3-haiku-20240307` |
| Follow-up generation | `claude-3-haiku-20240307` |
| Embeddings | `amazon.titan-embed-text-v2:0` (1536 dimensions) |
