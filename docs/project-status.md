# AIphaWatch — Project Status

**Version:** 1.0  
**Last Updated:** 2026-03-26  
**Lifecycle:** Phase 1 (MVP) underway — API skeleton running  
**Overall Status:** ✅ Phase 0 complete; 🔧 Phase 1 MVP in progress (Steps 1, 3 of 14 complete)  
**Deliverables Completed:** Product requirements document; full technical specification; LangGraph workflow designs (IngestionGraph, BriefGraph, ChatGraph, SentimentGraph); PostgreSQL schema with pgvector and RLS; FastAPI API contracts; React component tree; Celery job definitions; Terraform module layout; CI/CD pipeline spec; **Terraform infrastructure — 8 modules + staging/production environments**; **FastAPI skeleton — auth middleware, tenant context, health endpoint**

---

## Executive Summary

AIphaWatch gives buy-side analysts a single dashboard that answers: "What changed across my companies, and what does it mean?" Every Monday morning, Sarah opens the platform, sees a prioritized digest of her 12 watched companies — new SEC filings, price moves, sentiment shifts, risk flags — and drills into any company for a structured analyst brief with citations she can trust enough to act on. When the brief raises questions, she switches to a conversational chat interface grounded in the same source data to dig deeper.

The platform reduces per-company research time from hours to minutes, delivers citation-backed briefs where every claim links to a real source, and provides a professional-grade chat experience that remembers context across follow-up questions. Phase 1 (MVP) is underway — the goal is a demo-ready product where Sarah can watch companies, read briefs, and chat with the data.

---

## Current Focus

1. ~~**Terraform infrastructure scaffolding** — VPC, RDS, ElastiCache, Cognito, ECS, S3, CloudFront, Secrets Manager~~ ✅ Complete
2. **Database schema deployment** — all 12 tables, HNSW vector index, RLS policies ← **next**
3. ~~**FastAPI skeleton** — Cognito JWT middleware, tenant context injection, health endpoint~~ ✅ Complete

---

## Progress Snapshot

| Phase | Scope | Status | Notes |
|-------|-------|--------|-------|
| Phase 0 — Planning & Alignment | PRD, technical specification, architectural direction | ✅ Complete | All planning documents authored; 14-step Phase 1 build order defined |
| Phase 1 — MVP | Auth, watchlist, EDGAR ingestion, financial API, news, analyst briefs, chat, dashboard, infra | 🔧 In Progress | Steps 1 + 3 complete; database schema is next |
| Phase 2 — Intelligence Expansion | Full news depth, sentiment enrichment, risk flag detection, document upload, competitor lookup | ⏳ Planned | — |
| Phase 3 — SaaS Hardening | Tenant branding, alert notifications, admin panel, bulk import, brief export, usage tracking | ⏳ Planned | — |
| Phase 4 — Scale & Polish | Earnings transcripts, watchlist sharing, scheduled briefs, comparison views, audit log, API access | ⏳ Planned | — |

---

## Phase 1 — MVP Task Tracking

**Goal:** Sarah can watch 12 companies, see what changed, read analyst briefs, and chat with the data. Demo-ready.

- [x] Step 1: Terraform — VPC, RDS, Redis, Cognito, ECS, S3, CloudFront, Secrets (8 modules + staging/production)
- [ ] Step 2: Database schema — all tables, HNSW index, RLS policies
- [x] Step 3: FastAPI skeleton — Cognito JWT auth, TenantMiddleware, tenant-scoped DB sessions, health endpoint
- [ ] Step 4: Company resolution + Watchlist CRUD endpoints
- [ ] Step 5: EDGAR ingestion service + `IngestionGraph`
- [ ] Step 6: Financial API ingestion + `FinancialSnapshot` storage
- [ ] Step 7: Lightweight news ingestion + `SentimentGraph`
- [ ] Step 8: `BriefGraph` — all 8 sections with parallel fan-out
- [ ] Step 9: Brief API endpoint + React `BriefViewer`
- [ ] Step 10: `ChatGraph` + SSE streaming endpoint
- [ ] Step 11: React `ChatContainer` + streaming UI
- [ ] Step 12: Dashboard endpoint + React `WatchlistGrid`
- [ ] Step 13: `PeersChips` + competitor detection in chat
- [ ] Step 14: CI/CD pipeline + staging deployment

Steps 1–4 can be parallelized; Steps 5–8 are sequential; Steps 9–13 can be parallelized once APIs exist.

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM hallucination in analyst briefs | High | Medium | Citation-per-claim enforced in all prompts; post-generation validation that cited sources exist; "What changed" is data-driven (snapshot diffs, no LLM) |
| SEC EDGAR rate limits and parsing inconsistency across filers | Medium | High | Respectful crawling with exponential backoff; `content_hash` (SHA-256) deduplication to avoid re-processing; `unstructured` library for multi-format parsing |
| Free-tier financial API limits (Alpha Vantage: 25 req/day) insufficient at scale | Medium | High | Prioritize refresh by most-watched companies; display `last_updated_at` timestamps; plan migration to Polygon.io for production |
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

---

## References

- `docs/PRD-AIphaWatch-2026-03-25.md`
- `docs/AIphaWatch-TechnicalSpec.md`
- `developer/developer-journal.md`
- `README.md`
