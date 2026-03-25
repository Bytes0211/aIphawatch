# PRD: AIphaWatch

**Version:** 1.0
**Date:** 2026-03-25
**Author:** Steven Cotton
**Status:** Draft

---

## 1. Overview and Objectives

AIphaWatch is a SaaS platform that autonomously gathers, analyzes, and synthesizes financial intelligence across SEC filings, news articles, uploaded documents, and financial APIs — delivering structured analyst briefs with citations and a conversational chat interface for deep-dive research.

### The Story

Sarah is a buy-side analyst at a mid-size fund. Every Monday morning she opens the dashboard, sees a digest of what changed across her 12 watched companies over the weekend — earnings surprises, SEC filings, news sentiment shifts — and can drill into any company to chat with the underlying data.

### Objectives

- Reduce analyst research time from hours to minutes per company
- Deliver structured, citation-backed briefs that analysts trust enough to act on
- Provide a conversational interface that lets analysts ask follow-up questions grounded in real source data
- Support multi-tenant SaaS with tenant-configurable data sources, watchlists, alert thresholds, and branding
- Demo-ready from Phase 1 — the chat interface must look professional-grade immediately

---

## 2. Target Audience

### Primary: Buy-Side Analysts

- Work at mid-size funds (hedge funds, asset managers, PE firms)
- Track 10–50 companies across sectors
- Need to identify material changes quickly (filings, earnings, sentiment shifts)
- Value citations and source traceability — won't act on unsourced claims
- Currently spend 2–4 hours per company on Monday morning catch-up

### Secondary: Portfolio Managers

- Consume analyst briefs, don't generate them
- Want the executive summary and risk flags — skip the detail
- May use the chat interface for ad-hoc competitor comparisons

### Tenant Admins

- Configure data sources, branding, watchlists, and alert thresholds
- Manage team access and permissions

---

## 3. Core Features and Functionality

### 3.1 Watchlist Management

Users create and manage a watchlist of companies to monitor.

- **Add by ticker or company name** — auto-resolve to canonical entity (ticker, CIK, sector)
- **Watchlist limits** — tenant-configurable (default: 50 companies per user)
- **Sector tagging** — auto-assigned from financial API, user-overridable
- **Alert thresholds** — per-company configurable: price change %, sentiment shift, new filing types
- **Bulk import** — CSV upload for initial watchlist seeding

**Acceptance Criteria:**
- User can add a company by ticker or name and see it appear on their watchlist within 3 seconds
- System resolves ambiguous names (e.g., "Apple" → AAPL) with confirmation
- Alert thresholds persist per company and trigger notifications when breached
- Watchlist state syncs across sessions

### 3.2 Data Ingestion Pipeline

Autonomous agents pull data from multiple sources on a schedule and on-demand.

#### 3.2.1 SEC EDGAR Ingestion

- Pull 10-K, 10-Q, and 8-K filings for all watchlisted companies
- Parse filing text, extract key sections (risk factors, MD&A, financial statements)
- Chunk and embed for RAG retrieval
- Track filing dates to detect new filings since last session
- **Source:** SEC EDGAR FULL-TEXT Search API (free, no API key required)

**Acceptance Criteria:**
- New filings detected within 1 hour of publication on EDGAR
- Filing text chunked with section-level metadata (filing type, section name, date)
- Chunks retrievable via semantic search with source attribution

#### 3.2.2 Financial API Ingestion

- Pull current and historical market data: price, volume, market cap, P/E, debt-to-equity, analyst ratings
- Scheduled refresh (configurable: hourly during market hours, daily otherwise)
- Store time-series data for delta calculations ("what changed since last session")
- **Recommended source:** Alpha Vantage (free tier: 25 requests/day; premium for production) or Polygon.io

**Acceptance Criteria:**
- Snapshot bar metrics (price, % change, mkt cap, P/E, debt/equity, analyst rating) populated for all watchlisted companies
- Delta calculations accurate against prior session values
- Stale data flagged with retrieval timestamp

#### 3.2.3 News Ingestion

- Pull news articles for watchlisted companies from a general news API
- Score sentiment per article (-100 to +100) using LLM
- Aggregate sentiment score per company with source breakdown
- Track sentiment delta vs prior period
- **Recommended source:** NewsAPI.org or Tavily (already used in DealFinder)

**Acceptance Criteria:**
- News articles retrieved for all watchlisted companies within the configured schedule
- Sentiment scores reproducible (same article → same score ± 5 points)
- Source breakdown shows which articles drove the aggregate score

#### 3.2.4 Document Upload

- Users upload PDFs (10-K filings, research reports, internal memos)
- Parse, chunk, and embed uploaded documents
- Tag with company, document type, and upload date
- Available for RAG retrieval alongside ingested data

**Acceptance Criteria:**
- PDF upload completes within 30 seconds for files up to 50MB
- Uploaded document chunks retrievable in chat within 60 seconds of upload
- Source attribution in chat responses distinguishes uploaded docs from auto-ingested data

### 3.3 Analyst Brief Generation

The system generates a structured analyst brief per company, following the 8-section template.

#### Brief Template

| # | Section | Content | Category |
|---|---------|---------|----------|
| 1 | **Header** | Company, ticker, sector, date generated, session ID | Structural |
| 2 | **Snapshot bar** | Price, % change, mkt cap, P/E, debt/equity, analyst rating, sentiment score | Glanceable |
| 3 | **What changed** | Bullet deltas since last session: filings, earnings, news, price moves, guidance changes | Highest signal |
| 4 | **Risk flags** | Auto-surfaced anomalies: covenant mentions, litigation, guidance cuts, insider sells, schema drift | Auto-flagged |
| 5 | **Sentiment score** | News + earnings call tone, scored -100 to +100, delta vs prior period, source breakdown | Scored |
| 6 | **Executive summary** | 3–5 sentence LLM synthesis with citations, written for a PM who reads nothing else | Synthesized |
| 7 | **Sources & citations** | SEC filing links, news URLs, uploaded doc names, retrieval timestamps | Structural |
| 8 | **Suggested follow-ups** | 3 pre-seeded chat prompts auto-generated from the brief content | Actionable |

**Generation Logic:**
- "What changed" compares current ingested data against the user's last viewed session for that company
- "Risk flags" uses keyword detection + LLM classification on filing text and news (covenant mentions, litigation language, guidance cuts, insider sell patterns)
- "Sentiment score" aggregates per-article LLM sentiment scores, weighted by recency and source authority
- "Executive summary" is a 3–5 sentence LLM synthesis that cites specific sources (e.g., "[10-K §Risk Factors, 2026-01-15]")
- "Suggested follow-ups" are auto-generated from brief content (e.g., "What drove the 12% debt-to-equity increase?")

**Acceptance Criteria:**
- Brief generates within 15 seconds per company
- Every claim in the executive summary has at least one citation
- "What changed" is empty (not fabricated) when nothing actually changed
- Risk flags have zero tolerance for false negatives on litigation and guidance cuts

### 3.4 Conversational Chat Interface

The chat allows users to ask follow-up questions grounded in the company's ingested data via RAG.

#### Core Chat Behavior

- Multi-turn conversation with full session memory
- RAG retrieval over all ingested data for the active company (filings, news, financials, uploads)
- Every response cites sources with retrievable links
- Suggested follow-up prompts after each response

#### Three Memory Behaviors

| Behavior | Example | Implementation |
|----------|---------|----------------|
| **Entity memory** | Knows "Apple" is the focus without re-stating it | `active_company` in session state |
| **Conversation context** | "What about their margins?" — resolves "their" correctly | Full message history passed to LLM |
| **Retrieved chunk cache** | Doesn't re-fetch the 10-K on every follow-up | `retrieved_chunks` in session state; check before fetching |

The chunk cache is critical for performance and cost — it makes follow-up questions fast and saves LLM token costs by avoiding redundant retrieval and re-embedding of the same document chunks.

#### On-Demand Competitor Lookup

When a user asks a cross-company question (e.g., "How does Apple's debt-to-equity compare to Microsoft?"):

1. Detect the comparison entity (Microsoft) is not on the watchlist
2. Spin up a **lightweight parallel lookup** for the specific metric requested
3. Pull only the data needed to answer the question (not full ingestion)
4. Answer with citations from both sources
5. Do **not** add the comparison company to the watchlist or persist the data beyond the session

**Acceptance Criteria:**
- Chat response latency < 5 seconds for questions answerable from cached chunks
- Chat response latency < 15 seconds for questions requiring new retrieval
- On-demand competitor lookup completes within 10 seconds
- All responses include source citations
- Chunk cache hit rate > 70% within a multi-turn session on a single company
- Professional-grade UI from Phase 1 (see Section 6)

### 3.5 Dashboard — Monday Morning View

The landing page Sarah sees when she logs in.

- **Watchlist digest** — all watched companies, sorted by "most changed" since last session
- **Per-company summary cards** showing: ticker, name, sentiment delta, # of new filings, # of risk flags, price change %
- **Click-through** to full analyst brief for any company
- **Visual indicators** — color-coded badges for sentiment (green/yellow/red), new filings (blue dot), risk flags (red triangle)
- **Time range selector** — "since last login," "last 24h," "last 7 days"

**Acceptance Criteria:**
- Dashboard loads within 3 seconds with 50 companies
- Companies with material changes surface to the top
- Visual hierarchy makes it obvious which companies need attention

### 3.6 Multi-Tenant Configuration

Each tenant (organization) can configure:

| Setting | Scope | Default |
|---------|-------|---------|
| **Data sources** | Which APIs/feeds are active | All enabled |
| **Watchlist limits** | Max companies per user | 50 |
| **Alert thresholds** | Default price/sentiment thresholds | ±5% price, ±15 sentiment |
| **Branding** | Logo, primary color, accent color, custom domain (CNAME) | Platform defaults |
| **Ingestion schedule** | How often data refreshes | Hourly (market hours), daily (off-hours) |
| **Brief template** | Which sections are visible | All 8 sections |

**Acceptance Criteria:**
- Tenant admin can update all settings via an admin panel
- Branding changes reflect immediately across the tenant's UI
- Custom domain routes correctly with SSL

---

## 4. Technical Stack Recommendations

### Backend

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **API framework** | Python / FastAPI | Async-native, Pydantic validation, proven in production (DealFinder) |
| **LLM provider** | AWS Bedrock (Claude) | Managed, no endpoint ops, cross-region inference, pay-per-token |
| **Embeddings** | Amazon Titan Embeddings or OpenAI ada-002 | Low-cost, high-quality embeddings for RAG |
| **Vector database** | pgvector (PostgreSQL extension) | Single database for relational + vector, simpler ops than a separate vector DB |
| **Relational database** | PostgreSQL (RDS or Aurora) | Multi-tenant data, user state, watchlists, session history |
| **Agent orchestration** | LangGraph | Centerpiece technology. Owns all stateful, multi-step agent workflows: brief generation (fan-out across data sources → merge → synthesize), competitor lookup (detect entity → parallel fetch → answer), and chat agent (RAG retrieval → chunk cache check → LLM call → citation injection). Graph-based orchestration provides explicit state management, conditional branching, and human-in-the-loop hooks that plain prompt chains cannot. |
| **Task scheduling** | Celery + Redis | Owns time-based background jobs: scheduled ingestion runs, watchlist refresh cycles, stale data cleanup. LangGraph owns the _workflow logic_; Celery owns the _clock_. |
| **Document parsing** | PyMuPDF + unstructured | PDF text extraction and chunking |
| **Cache** | Redis | Session state, chunk cache, rate limit tracking |

### Frontend

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Framework** | React + TypeScript | Industry standard, strong component ecosystem |
| **UI library** | shadcn/ui + Tailwind CSS | Professional-grade components, highly customizable for tenant branding |
| **Charts** | Recharts or Tremor | Financial data visualization (snapshot bar, sentiment trends) |
| **Chat UI** | Custom component (streaming SSE) | Professional-grade chat with streaming responses, citations, suggested prompts |
| **State management** | TanStack Query + Zustand | Server state caching + lightweight client state |

### Infrastructure

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Cloud** | AWS | Bedrock integration, existing expertise |
| **Deployment** | ECS Fargate (API) + S3/CloudFront (frontend) | Containerized backend, static frontend |
| **Auth** | Cognito or Auth0 | Multi-tenant auth with org-level isolation |
| **IaC** | Terraform | Reproducible environments |
| **CI/CD** | GitHub Actions | Automated testing and deployment |

---

## 5. Conceptual Data Model

### Core Entities

```
Tenant
├── id (UUID, PK)
├── name (string)
├── slug (string, unique) — used for subdomain routing
├── branding (JSONB) — logo_url, primary_color, accent_color, custom_domain
├── config (JSONB) — watchlist_limit, default_thresholds, ingestion_schedule, active_sources
├── created_at, updated_at

User
├── id (UUID, PK)
├── tenant_id (UUID, FK → Tenant)
├── email (string, unique per tenant)
├── role (enum: admin, analyst, viewer)
├── preferences (JSONB) — alert settings, dashboard layout
├── last_login_at (timestamp)
├── created_at, updated_at

Company
├── id (UUID, PK)
├── ticker (string, unique)
├── name (string)
├── sector (string)
├── cik (string, nullable) — SEC EDGAR identifier
├── metadata (JSONB) — exchange, industry, description
├── created_at, updated_at

Watchlist
├── id (UUID, PK)
├── user_id (UUID, FK → User)
├── company_id (UUID, FK → Company)
├── alert_thresholds (JSONB) — price_change_pct, sentiment_shift, filing_types
├── created_at

Document
├── id (UUID, PK)
├── company_id (UUID, FK → Company)
├── source_type (enum: edgar_10k, edgar_10q, edgar_8k, news, upload, financial_api)
├── source_url (string, nullable)
├── title (string)
├── content_hash (string) — deduplication
├── raw_text (text)
├── metadata (JSONB) — filing_date, section_name, author, sentiment_score
├── ingested_at (timestamp)
├── created_at

DocumentChunk
├── id (UUID, PK)
├── document_id (UUID, FK → Document)
├── company_id (UUID, FK → Company)
├── chunk_index (integer)
├── content (text)
├── embedding (vector(1536))
├── metadata (JSONB) — section, page_number, token_count
├── created_at

FinancialSnapshot
├── id (UUID, PK)
├── company_id (UUID, FK → Company)
├── snapshot_date (date)
├── price (decimal)
├── price_change_pct (decimal)
├── market_cap (bigint)
├── pe_ratio (decimal, nullable)
├── debt_to_equity (decimal, nullable)
├── analyst_rating (string, nullable)
├── raw_data (JSONB) — full API response
├── created_at

SentimentRecord
├── id (UUID, PK)
├── company_id (UUID, FK → Company)
├── document_id (UUID, FK → Document)
├── score (integer) — -100 to +100
├── source_type (string) — news, earnings_call, filing
├── scored_at (timestamp)

AnalystBrief
├── id (UUID, PK)
├── user_id (UUID, FK → User)
├── company_id (UUID, FK → Company)
├── session_id (UUID) — groups briefs from same session
├── generated_at (timestamp)

BriefSection
├── id (UUID, PK)
├── brief_id (UUID, FK → AnalystBrief)
├── section_type (enum: header, snapshot, what_changed, risk_flags, sentiment, executive_summary, sources, suggested_followups)
├── section_order (integer) — 1–8, matches template order
├── content (JSONB) — structured content for this section (schema varies by type)
├── created_at
    Note: Splitting sections into their own table enables querying individual sections
    (e.g., "show all risk flags across my watchlist"), diffing briefs across sessions
    ("what changed in the What Changed section since last week"), and exporting
    specific sections without deserializing the entire brief.

ChatSession
├── id (UUID, PK)
├── user_id (UUID, FK → User)
├── company_id (UUID, FK → Company)
├── active_company_ticker (string) — entity memory
├── messages (JSONB[]) — full conversation history (append-only)
├── context_summary (text, nullable) — rolling LLM-generated summary of older messages
├── context_summary_through (integer, nullable) — message index up to which the summary covers
├── retrieved_chunk_ids (UUID[]) — chunk cache for cost optimization
├── created_at, updated_at
    Note: Messages array grows unbounded in long sessions. To keep Bedrock token
    costs and latency under control, the LLM receives: context_summary (covering
    messages 0..N) + the last 10 raw messages (N+1..current) + retrieved chunks.
    When message count exceeds 20, a background summarization pass compresses
    older messages into context_summary. Full message history is retained in the
    array for audit/export but is NOT passed to the LLM on every turn.

RiskFlag
├── id (UUID, PK)
├── company_id (UUID, FK → Company)
├── document_id (UUID, FK → Document, nullable)
├── flag_type (enum: covenant, litigation, guidance_cut, insider_sell, schema_drift)
├── severity (enum: low, medium, high, critical)
├── description (text)
├── detected_at (timestamp)
```

### Key Relationships

- Tenant → Users (1:many)
- User → Watchlist → Companies (many:many through Watchlist)
- Company → Documents → DocumentChunks (1:many:many)
- Company → FinancialSnapshots (1:many, time-series)
- Company → SentimentRecords (1:many)
- User + Company → AnalystBriefs (per session)
- User + Company → ChatSessions (1:many)

### Multi-Tenant Isolation

- All queries scoped by `tenant_id` at the repository layer
- Row-level security (RLS) in PostgreSQL as defense-in-depth
- Vector search scoped by `company_id` (which maps to tenant through watchlist)

---

## 6. UI Design Principles

### Professional-Grade Chat — Phase 1 Priority

The chat interface is the demo surface. It must look and feel production-ready from day one.

- **Streaming responses** — text appears word-by-word via SSE, not as a block after generation completes
- **Inline citations** — clickable source references within the response text (e.g., `[10-K §Risk Factors]` opens the source)
- **Suggested prompts** — 3 clickable follow-up chips below each response, auto-generated from context
- **Company context indicator** — persistent header showing active company (ticker, name, last updated)
- **Message types** — distinct visual treatment for user messages, AI responses, system messages (e.g., "Fetching Microsoft data for comparison...")
- **Loading states** — skeleton loaders for brief generation, typing indicator for chat, progress indicator for document upload
- **Dark/light mode** — respect system preference, tenant-overridable

### Dashboard Design

- **Card-based layout** — one card per watched company, scannable at a glance
- **Visual priority** — companies with material changes rise to top, color-coded severity
- **Responsive** — desktop-first but usable on tablet (analysts occasionally use iPads in meetings)

### Tenant Branding

- Logo placement in nav bar and login screen
- Primary color applied to buttons, links, active states
- Accent color for highlights and badges
- Custom domain with tenant SSL certificate
- Branding preview in admin panel before publishing

---

## 7. Security Considerations

### Authentication & Authorization

- **Auth provider:** AWS Cognito or Auth0 with organization-level isolation
- **Session management:** JWT tokens with short expiry (15 min) + refresh tokens
- **Role-based access:** Admin (tenant config + user management), Analyst (full feature access), Viewer (read-only briefs and chat)
- **MFA:** Required for admin roles, optional for analysts (tenant-configurable)

### Data Isolation

- **Tenant isolation:** All database queries scoped by tenant_id; RLS as defense-in-depth
- **Vector search isolation:** Chunks scoped by company_id, which maps to tenant through watchlist
- **Upload isolation:** Uploaded documents stored in tenant-scoped S3 prefixes
- **Chat history:** Session data scoped to user; no cross-user visibility

### External API Security

- **API keys** stored in AWS Secrets Manager, never in code or environment variables
- **EDGAR access:** No API key required, but respect SEC rate limits (10 req/sec, identify with User-Agent)
- **Financial APIs:** Key rotation policy, usage monitoring for abuse detection
- **LLM (Bedrock):** IAM role-based access, no API keys in application code

### Data Handling

- **PII:** System does not intentionally ingest PII; uploaded documents may contain it — flag in upload flow
- **Retention:** Tenant-configurable retention policies for chat history and ingested documents
- **Encryption:** At rest (RDS/S3 encryption) and in transit (TLS 1.3)

---

## 8. Development Phases

### Phase 1 — MVP

**Goal:** Sarah can watch 12 companies, see what changed, read analyst briefs, and chat with the data. Demo-ready.

| Feature | Details |
|---------|---------|
| **Auth & multi-tenancy** | Cognito/Auth0 setup, tenant isolation, basic RBAC (admin + analyst) |
| **Watchlist** | Add/remove companies by ticker, per-company alert thresholds |
| **EDGAR ingestion** | 10-K, 10-Q, 8-K parsing and chunking for watchlisted companies |
| **Financial API** | Snapshot bar metrics (price, % change, mkt cap, P/E, debt/equity) via Alpha Vantage or Polygon |
| **Lightweight news ingestion** | Pull recent headlines for watchlisted companies via NewsAPI/Tavily. Basic LLM sentiment scoring (-100 to +100) per article. Enables the sentiment score in the snapshot bar and brief so the demo tells a complete story. Full news depth (source breakdown, weighted scoring, historical tracking) deferred to Phase 2. |
| **Analyst brief** | Full 8-section template generation per company |
| **Chat (professional-grade UI)** | Multi-turn RAG chat with entity memory, conversation context, chunk cache, streaming responses, inline citations, suggested follow-ups |
| **Dashboard** | Monday morning view — watchlist digest sorted by most changed |
| **Infrastructure** | Terraform, CI/CD, staging + production environments |

**Not in Phase 1:** Full news depth (weighted scoring, historical tracking, source breakdown), on-demand competitor lookup, custom branding, alerts/notifications, document upload.

### Phase 2 — Intelligence Expansion 

| Feature | Details |
|---------|---------|
| **Full news depth** | Expand Phase 1 lightweight news: weighted scoring by source authority and recency, historical sentiment tracking, source breakdown visualization |
| **Sentiment enrichment** | Sentiment delta vs prior period, trend charts, per-source breakdown in brief |
| **Risk flag detection** | LLM classification on filings/news for litigation, covenant, guidance cut, insider sell |
| **Document upload** | PDF upload, parse, chunk, embed, available in RAG |
| **On-demand competitor lookup** | Lightweight parallel fetch for cross-company chat questions |

### Phase 3 — SaaS Hardening

| Feature | Details |
|---------|---------|
| **Tenant branding** | Logo, colors, custom domain (CNAME + SSL) |
| **Alert notifications** | Email/Slack alerts when thresholds breached |
| **Admin panel** | Tenant config UI (sources, limits, thresholds, branding, user management) |
| **Bulk watchlist import** | CSV upload for initial seeding |
| **Brief export** | PDF/Markdown export of analyst briefs |
| **Usage tracking** | Per-tenant usage metrics (API calls, LLM tokens, storage) for billing |

### Phase 4 — Scale & Polish

| Feature | Details |
|---------|---------|
| **Earnings call transcripts** | Ingest and analyze earnings call transcripts as a data source |
| **Watchlist sharing** | Team-level shared watchlists within a tenant |
| **Scheduled briefs** | Auto-generate and email briefs on a schedule (Monday 7 AM) |
| **Comparison views** | Side-by-side company comparison in the UI (not just chat) |
| **Audit log** | Track all user actions for compliance |
| **API access** | Tenant API keys for programmatic brief generation |

---

## 9. Potential Challenges and Solutions

### Challenge: LLM Hallucination in Briefs

**Risk:** Claude generates plausible but incorrect claims in the executive summary or risk flags.
**Mitigation:** Every claim must trace to a retrieved chunk. The brief generation prompt enforces citation-per-claim. Post-generation validation checks that cited sources exist and contain supporting text. "What changed" section is data-driven (diffing snapshots), not LLM-generated.

### Challenge: SEC EDGAR Rate Limits and Parsing

**Risk:** EDGAR enforces 10 requests/second. Parsing 10-K filings (100+ pages) is complex and inconsistent across filers.
**Mitigation:** Respectful crawling with backoff. Use the EDGAR full-text search API for detection, then fetch individual filings. Cache parsed filings by content hash to avoid re-processing. Use `unstructured` library for robust parsing across filing formats.

### Challenge: Stale Financial Data

**Risk:** Free-tier financial APIs have daily limits (Alpha Vantage: 25/day) which may not cover all watchlisted companies.
**Mitigation:** Prioritize refresh by "most watched" companies. Display retrieval timestamps prominently. Use Polygon.io or paid tiers for production. The snapshot bar clearly labels when data was last updated.

### Challenge: Chunk Cache Invalidation

**Risk:** Chunk cache serves stale data after new filings are ingested.
**Mitigation:** Cache keyed by `(company_id, document_id, chunk_id)`. When new documents are ingested for a company, invalidate that company's chunk cache in all active sessions. Retrieval timestamps in citations make staleness visible.

### Challenge: Multi-Tenant Data Isolation

**Risk:** Cross-tenant data leakage through vector search or shared company records.
**Mitigation:** Companies are global entities (AAPL is AAPL), but watchlists, briefs, chat sessions, and uploaded documents are tenant-scoped. Vector search filters by company_id set, which is derived from the user's watchlist. RLS as defense-in-depth.

### Challenge: On-Demand Competitor Lookup Latency

**Risk:** Fetching financial data for a non-watchlisted company mid-conversation may be slow.
**Mitigation:** Parallel API calls for the specific metric requested (not full ingestion). Cache the lookup result for the session duration. Show a loading indicator ("Fetching Microsoft's debt-to-equity...") so the user knows it's working.

---

## 10. Future Expansion Possibilities

- **Custom LLM fine-tuning** — Fine-tune on a fund's historical research notes for domain-specific language
- **Slack/Teams integration** — Push brief summaries and alerts to team channels
- **Mobile app** — Read-only brief viewer + push notifications for alerts
- **Multi-language support** — Briefs and chat in the user's preferred language
- **Sector-level analysis** — Aggregate briefs across all companies in a sector for macro views
- **Backtesting** — "What did the brief look like 6 months ago?" for model validation
- **Plugin architecture** — Third-party data source connectors (Bloomberg, Refinitiv, S&P Capital IQ)
- **Compliance mode** — Audit trail, data retention policies, SOC 2 readiness for enterprise clients
