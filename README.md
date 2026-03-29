# AIphaWatch

![Phase 1](https://img.shields.io/badge/phase-1%20MVP-complete-brightgreen?style=flat-square)
![Phase 2](https://img.shields.io/badge/phase-2%20intelligence-kickoff-blue?style=flat-square)
![Status](https://img.shields.io/badge/status-execution%20planning-yellow?style=flat-square)
![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)
![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-FF9900?style=flat-square&logo=amazonaws&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20+%20pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?style=flat-square&logo=terraform&logoColor=white)
[![CI](https://img.shields.io/github/actions/workflow/status/Bytes0211/aIphawatch/ci.yml?branch=main&style=flat-square&label=CI&logo=githubactions&logoColor=white)](https://github.com/Bytes0211/aIphawatch/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

AI-powered equity intelligence for buy-side analysts.

AIphaWatch is a multi-tenant SaaS platform that ingests SEC EDGAR filings, financial data, and news to generate structured AI analyst briefs and power a conversational RAG chat interface — reducing company research from hours to minutes.

---

## Features

- **Analyst Briefs** — 8-section AI-generated briefs (snapshot, what changed, risk flags, sentiment, executive summary) via LangGraph + AWS Bedrock. Fan-out parallelism keeps P95 generation under 15 s.
- **RAG Chat** — Multi-turn conversational interface grounded in real EDGAR source data. Responses stream sentence-by-sentence via Server-Sent Events with inline citations.
- **Chunk Cache** — `retrieved_chunk_ids` persisted in `ChatSession` avoids re-embedding on follow-up questions. Target >70% cache hit rate per session.
- **Rolling Context Summary** — Conversations beyond 20 messages are compressed into a rolling summary (~300 tokens) so the LLM context window stays bounded regardless of session length.
- **Watchlist Dashboard** — Monday-morning digest sorted by most material changes across your tracked companies.
- **Automated Ingestion** — SEC EDGAR filings, financial snapshots (Alpha Vantage), and news (NewsAPI) ingested on schedule via Celery + Redis.
- **Multi-Tenant** — Tenant isolation enforced at the repository layer with PostgreSQL RLS as defence-in-depth.
- **Citation-Backed** — Every claim in the executive summary traces to a retrieved source chunk. Hallucinated citations are dropped post-generation.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + shadcn/ui + Tailwind CSS |
| API | Python / FastAPI + Uvicorn |
| Agent Orchestration | LangGraph + AWS Bedrock (Claude 3.5 Sonnet / Haiku) |
| Scheduler | Celery + Redis |
| Database | PostgreSQL 16 (RDS) + pgvector |
| Embeddings | Amazon Titan Embeddings v2 (1536-dim) |
| Auth | AWS Cognito (JWT, multi-tenant) |
| Storage | S3 |
| IaC | Terraform |
| CI/CD | GitHub Actions |

---

## Agent Architecture

LangGraph owns all stateful, multi-step workflows. Celery owns the clock. They meet at a well-defined boundary: Celery enqueues a task with an input payload; LangGraph executes the graph and writes results to Postgres.

### BriefGraph — fan-out / fan-in

Five section builders run **in parallel** via LangGraph `Send` after chunk retrieval. The executive summary runs last, after fan-in, so it can only synthesise information that was surfaced in the parallel sections.

```
retrieve_chunks          (Titan Embeddings v2 → pgvector cosine search, top-8 EDGAR chunks)
    └─ Send (parallel fan-out)
        ├─ build_snapshot        (data-driven — latest FinancialSnapshot, no LLM)
        ├─ build_what_changed    (data-driven — snapshot diff, 0.5% threshold, no LLM)
        ├─ build_risk_flags      (Claude Sonnet — up to 5 flags, sorted by severity)
        ├─ build_sentiment       (data-driven — pre-computed SentimentRecord aggregates)
        └─ build_sources         (data-driven — deduplicated citation list)
    └─ assemble_sections         (fan-in — collects and sorts all parallel outputs)
        └─ build_executive_summary   (Claude Sonnet — synthesises sections, citation guard)
            └─ build_suggested_followups  (Claude Haiku — 4 follow-up chips)
                └─ store_brief       (persists AnalystBrief + BriefSection rows)
                    └─ handle_errors → END
```

### ChatGraph — conditional routing

```
prepare_context          (loads ChatSession from DB; builds context window:
                          rolling summary + last 10 raw messages)
    └─ detect_intent     (Claude Haiku — 'rag' | 'comparison' | 'general';
                          falls back to 'rag' on any error)
        ├─ (rag / comparison) → check_chunk_cache
        │       ├─ (cache hit,  >70% target) ──────────────────────→ generate_response
        │       └─ (cache miss) → retrieve_chunks
        │               ├─ (comparison) → competitor_lookup          → generate_response
        │               └─ (no comparison)                          → generate_response
        └─ (general) ──────────────────────────────────────────→ generate_response
    └─ generate_response     (Claude Sonnet — context + chunks + competitor data + question)
        └─ generate_followups    (Claude Haiku — 3 follow-up chips)
            └─ persist_turn      (appends messages; merges new chunk IDs into cache)
                └─ maybe_summarize   (Claude Haiku — triggers at >20 msgs)
                    └─ handle_errors → END
```

### SSE Event Stream

`POST /api/chat/sessions/{session_id}/messages` streams a sequence of Server-Sent Events:

```
data: {"type": "token",     "token": "Apple's revenue grew..."}   ← one per sentence
data: {"type": "token",     "token": "...12% year-over-year. "}
data: {"type": "citations", "citations": [{"chunk_id": "...", "title": "Apple 10-K 2025", "source_type": "edgar_10k", "source_url": "...", "excerpt": "..."}]}
data: {"type": "followups", "questions": ["What drove the growth?", "How do margins compare YoY?", "What is the capex outlook?"]}
data: {"type": "done",      "session_id": "<uuid>"}

# On error:
data: {"type": "error",     "message": "An unexpected error occurred. Please try again."}
```

Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`

### SentimentGraph

```
fetch_news → parse_articles → store_articles → score_sentiments → store_sentiments → handle_errors → END
    └─ (no articles found) ──────────────────────────────────────────────────────→ handle_errors
```

### IngestionGraph

```
fetch_filings → parse_documents → chunk_documents → embed_chunks → store_chunks → handle_errors → END
    └─ (no new filings) ──────────────────────────────────────────────────────→ handle_errors
```

---

## API Endpoints

### Implemented

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | ALB health check | none |
| `GET` | `/api/companies/resolve?q={query}` | Resolve ticker/name to canonical company | analyst |
| `GET` | `/api/companies/{company_id}` | Get company by UUID | analyst |
| `GET` | `/api/watchlist` | List user watchlist with company data | analyst |
| `POST` | `/api/watchlist` | Add company by ticker | analyst |
| `DELETE` | `/api/watchlist/{company_id}` | Remove from watchlist | analyst |
| `POST` | `/api/ingestion/trigger` | Manually trigger EDGAR ingestion | admin |
| `GET` | `/api/companies/{company_id}/brief` | Get latest brief with all sections | analyst |
| `POST` | `/api/companies/{company_id}/brief/generate` | Force-generate a new brief | analyst |
| `GET` | `/api/companies/{company_id}/briefs` | List recent briefs (metadata only) | analyst |
| `GET` | `/api/companies/{company_id}/brief/{brief_id}/sections` | Get sections for a specific brief | analyst |
| `POST` | `/api/chat/sessions` | Create new chat session | analyst |
| `GET` | `/api/chat/sessions?company_id={id}` | List sessions for a company | analyst |
| `GET` | `/api/chat/sessions/{session_id}` | Get session metadata | analyst |
| `DELETE` | `/api/chat/sessions/{session_id}` | Delete session (ownership-enforced, 204) | analyst |
| `GET` | `/api/chat/sessions/{session_id}/messages` | Get full message history | analyst |
| `POST` | `/api/chat/sessions/{session_id}/messages` | Send message — returns SSE stream | analyst |
| `GET` | `/api/dashboard` | Watchlist digest sorted by most changed | analyst |

### Step 11 Frontend Streaming UI (Implemented)

The React chat streaming UI is implemented under `src/` with a container-driven architecture, Zustand state, and SSE parsing utilities:

- `src/components/chat/ChatContainer.tsx` — session lifecycle + send flow orchestration
- `src/components/chat/MessageList.tsx` — scrollable message thread with stable message keys
- `src/components/chat/MessageBubble.tsx` — role-based rendering, citations, follow-ups, streaming indicator
- `src/components/chat/InlineCitation.tsx` — inline source link rendering
- `src/components/chat/FollowUpChips.tsx` — clickable follow-up prompts
- `src/components/chat/CompanyContextBanner.tsx` — active company context header
- `src/components/chat/StreamingIndicator.tsx` — typing/streaming visual state
- `src/components/chat/ChatInput.tsx` — composer with send controls
- `src/hooks/useSSE.ts` — SSE fetch stream reader + event dispatch (`token`, `citations`, `followups`, `done`, `error`)
- `src/stores/chatStore.ts` — Zustand store for messages/session/streaming and stream lifecycle actions (`startAssistantStream`, `appendToken`, `finishStream`, `failStream`)
- `src/lib/sse.ts` — typed SSE event parsing
- `src/lib/api.ts` — typed API wrappers for session and message calls

PR hardening fixes included in Step 11:
- Empty placeholder assistant bubble on fetch failure is handled via `failStream(errorText)` (no blank bubble remains)
- Message list uses stable generated `id` keys (no array-index keys)
- Cross-company stale messages are cleared by resetting store state when navigating to a company without a pre-existing session

---

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended for environment management)
- Node.js 20+
- Docker Engine + Docker Compose plugin
- AWS CLI configured with appropriate credentials
- Terraform 1.6+

### Local Infrastructure (Required)

Start PostgreSQL (with pgvector) and Redis:

```bash
docker compose up -d postgres redis
```

Validate both are healthy:

```bash
docker compose ps
```

The local compose defaults match application defaults in `alphawatch/config.py`:

- Postgres: `localhost:5432`, database `alphawatch`, user `alphawatch`
- Redis: `localhost:6379`

Stop services when done:

```bash
docker compose down
```

### Backend

```bash
# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Run the API server
uv run uvicorn alphawatch.api.main:app --reload

# Verify health endpoint
curl http://localhost:8000/health
# {"status": "ok"}
```

### Frontend

```bash
npm install
npm run dev
```

### Infrastructure

The `infra/` directory contains 8 Terraform modules and 2 environment configurations:

```bash
# Initialize and deploy staging
cd infra/environments/staging
terraform init
terraform plan
terraform apply

# Initialize and deploy production
cd infra/environments/production
terraform init
terraform plan
terraform apply
```

**Modules:** `vpc`, `rds`, `elasticache`, `ecs`, `s3`, `cognito`, `cloudfront`, `secrets`  
**Environments:** `staging` (cost-optimized), `production` (Multi-AZ, auto-scaling)

---

## CI/CD (Step 14)

GitHub Actions workflows are defined under `.github/workflows/`:

- `ci.yml` — PR + main quality gates (pytest, mypy, ruff, frontend tests, TS typecheck)
- `build-artifacts.yml` — reusable image build/push + frontend build artifact
- `deploy-staging.yml` — main branch deploy to staging via Terraform + ECS stability waits + smoke tests
- `release-prod.yml` — production release via tag/manual trigger (no approval gate for solo operation)

### Required GitHub Repository Variables

- `AWS_REGION` — AWS region (e.g. `us-east-1`)
- `AWS_ROLE_ARN_STAGING` — OIDC-assumable role for staging deploy
- `AWS_ROLE_ARN_PRODUCTION` — OIDC-assumable role for production deploy
- `ECR_API_REPOSITORY` — ECR repo name for API image
- `ECR_WORKER_REPOSITORY` — ECR repo name for worker image
- `DEPLOY_FRONTEND_STATIC` — optional (`true`/`false`); static S3 sync only when enabled

### Rollback Quick Commands

```bash
# 1) Re-run Terraform apply with previous known-good image tags
cd infra/environments/staging
terraform init
terraform apply \
    -var "api_image=<known-good-api-image-uri>" \
    -var "worker_image=<known-good-worker-image-uri>"

# 2) Wait for ECS services to stabilize
aws ecs wait services-stable --cluster <cluster-name> --services <api-service-name>
aws ecs wait services-stable --cluster <cluster-name> --services <worker-service-name>

# 3) Verify health endpoint
curl --fail http://<alb-dns-name>/health
```

---

## Testing

```bash
# Backend tests
uv run pytest tests/ -v

# Backend with coverage
uv run pytest tests/ --cov=alphawatch --cov-report=term-missing

# Type checking
mypy alphawatch/

# Linting
ruff check alphawatch/

# Frontend tests
npm test

# Frontend type checking
npx tsc --noEmit
```

### Test Coverage by Module

| Test File | Scope | Tests |
|---|---|---|
| `test_models.py` | ORM model registration + structure | 30 |
| `test_config.py` | Settings defaults, computed URLs, env overrides | 14 |
| `test_auth.py` | Bearer token extraction, `AuthError` | 9 |
| `test_dependencies.py` | `get_current_user`, `require_role` RBAC | 8 |
| `test_api.py` | Health endpoint, middleware auth, schemas | 10 |
| `test_companies.py` | Company schemas, auth enforcement, routing | 10 |
| `test_watchlist.py` | Watchlist schemas, auth enforcement, routing | 12 |
| `test_ingestion.py` | State types, chunker, EDGAR mapping, graph, endpoint | 29 |
| `test_financial.py` | Safe parsing, data classes, schemas, client, config | 25 |
| `test_sentiment.py` | NewsClient, BedrockClient, SentimentGraph, repository | 34 |
| `test_brief.py` | BriefState types, all nodes, BriefGraph, repositories | 71 |
| `test_chat.py` | ChatState types, all nodes, routing, repository, schemas, API | 95 |
| `test_briefs_api.py` | Brief API schemas and routing | 13 |
| `test_dashboard.py` | Dashboard schemas, routing, repository coverage | 26 |
| **Total** | | **401** |

---

## Project Status

| Phase | Status | Description |
|---|---|---|
| Phase 1 — MVP | ✅ Complete | Auth, watchlist, EDGAR ingestion, financial API, news, briefs, chat, dashboard, infra |
| Phase 2 — Intelligence | 🔧 In Progress | Full news depth, sentiment enrichment, risk flags, document upload, comparative intelligence |
| Phase 3 — SaaS Hardening | ⏳ Planned | Tenant branding, alerts, admin panel, bulk import, brief export, usage tracking |
| Phase 4 — Scale & Polish | ⏳ Planned | Earnings transcripts, watchlist sharing, scheduled briefs, comparison views, audit log |

### Phase 1 Build Order

- [x] Step 1: Terraform — VPC, RDS, Redis, Cognito, ECS, S3, CloudFront, Secrets
- [x] Step 2: Database schema — 12 ORM models, Alembic migration, HNSW index, RLS policies
- [x] Step 3: FastAPI skeleton — Cognito JWT auth, TenantMiddleware, health endpoint
- [x] Step 4: Company resolution + Watchlist CRUD endpoints
- [x] Step 5: EDGAR ingestion — `IngestionGraph`, EDGAR client, chunker, embeddings
- [x] Step 6: Financial API — Alpha Vantage client, `FinancialSnapshot` repository
- [x] Step 7: News ingestion — NewsAPI client, BedrockClient, `SentimentGraph`
- [x] Step 8: `BriefGraph` — all 8 sections with parallel fan-out
- [x] Step 9: Brief API endpoints + Pydantic schemas
- [x] Step 10: `ChatGraph` + SSE streaming endpoint
- [x] Step 11: React `ChatContainer` + streaming UI
- [x] Step 12: Dashboard endpoint + React `WatchlistGrid`
- [x] Step 13: `PeersChips` + competitor detection in chat
- [x] Step 14: CI/CD pipeline + staging deployment

### Phase 2 Build Order

- [ ] Step 1: Platform hardening baseline — IAM least-privilege cleanup, reproducible build locks, deployment guardrails
- [ ] Step 2: Runtime foundations rollout — provider factory wiring, config-driven selection, and chat summarization off the hot path
- [ ] Step 3: Full news ingestion depth — multi-source adapters, stronger deduplication, per-source quotas
- [ ] Step 4: Sentiment enrichment v2 — entity/aspect tagging, confidence scoring, trend normalization
- [ ] Step 5: Risk flag pipeline v2 — richer categories, deterministic severity calibration, persistence upgrades
- [ ] Step 6: Document upload ingestion — tenant-scoped upload API, parser/chunker/embed/store workflow
- [ ] Step 7: Hybrid retrieval policy — blend EDGAR and uploaded sources with source weighting and controls
- [ ] Step 8: Comparative intelligence expansion — competitor benchmark cards and comparison-aware prompt routing
- [ ] Step 9: Brief delta intelligence — cross-brief section diffs and "what materially changed" attribution
- [ ] Step 10: Alerts and delivery channels — threshold/rule engine plus email/slack delivery
- [ ] Step 11: Evaluation harness and quality gates — golden datasets, response scoring, regression checks in CI
- [ ] Step 12: Phase 2 release hardening — staging soak, runbooks, rollback drills, production cutover

---

## Documentation

- [`docs/PRD-AIphaWatch-2026-03-25.md`](docs/PRD-AIphaWatch-2026-03-25.md) — Product requirements
- [`docs/AIphaWatch-TechnicalSpec.md`](docs/AIphaWatch-TechnicalSpec.md) — Technical specification
- [`docs/project-status.md`](docs/project-status.md) — Detailed phase and step tracking
- [`AGENTS.md`](AGENTS.md) — AI agent guidance, graph shapes, and architecture reference
- [`developer/developer-journal.md`](developer/developer-journal.md) — Development log
- [`docs/phase2-step1-hardening.md`](docs/phase2-step1-hardening.md) — Step 1 execution checklist (IAM, CI gates, deploy guardrails, migration drill)
- [`docs/phase2-step2-runtime-foundations-spec.md`](docs/phase2-step2-runtime-foundations-spec.md) — Step 2 architecture and execution spec
- [`docs/phase2-step3-news-ingestion-spec.md`](docs/phase2-step3-news-ingestion-spec.md) — Step 3 multi-source ingestion spec
- [`docs/phase2-operations-runbook-news-sources.md`](docs/phase2-operations-runbook-news-sources.md) — News source operations runbook
- [Phase 2 Epic (GitHub issue)](https://github.com/Bytes0211/aIphawatch/issues/26) — Phase 2 epic and issue breakdown
- [Phase 2 Project (GitHub)](https://github.com/users/Bytes0211/projects/2) — Phase 2 project board

---

## License

[MIT](LICENSE)