# Phase 2 Step 3 — Full News Ingestion Depth (Spec)

## Purpose

Expand news ingestion from single-source lightweight collection to resilient multi-source ingestion with deduplication and quota-aware controls.

---

## Scope

### In scope

1. Multi-source news adapter architecture.
2. Source-aware normalization and cross-source deduplication.
3. Per-source quota/rate controls and graceful fallback.
4. Metadata enrichment to support downstream sentiment weighting.

### Out of scope

1. Full sentiment model redesign (Step 4).
2. Hybrid retrieval blending with uploaded docs (Step 7).

---

## Current State

1. Single NewsAPI client in [alphawatch/services/news.py](alphawatch/services/news.py).
2. Sentiment flow entry in `fetch_news` node at [alphawatch/agents/nodes/sentiment.py](alphawatch/agents/nodes/sentiment.py).
3. Sentiment graph routing in [alphawatch/agents/graphs/sentiment.py](alphawatch/agents/graphs/sentiment.py).

---

## Target Architecture

### A. Adapter model

1. Define a common adapter interface for providers.
2. Normalize all provider payloads into a shared article schema.
3. Preserve provider identity and source metadata.

### B. Deduplication model

1. Canonical URL normalization primary key.
2. Secondary fallback key from normalized title + publication window.
3. Cross-source dedup performed after provider merge.

### C. Quota and fallback model

1. Per-provider daily/hourly budget controls from config.
2. Provider failures and quota exhaustion do not fail full ingestion.
3. Partial results continue through sentiment pipeline.

---

## Implementation Plan

### Workstream 1: Adapter refactor

1. Extract provider interface and move NewsAPI into adapter implementation.
2. Add second provider adapter behind config flag.
3. Merge adapter outputs via orchestrator function.

### Workstream 2: Dedup and enrichment

1. Implement canonicalization utility.
2. Apply cross-source dedup merge policy.
3. Attach metadata fields for source, confidence hints, and normalized identifiers.

### Workstream 3: Pipeline integration

1. Update `fetch_news` node to call orchestrator.
2. Ensure no-article routing still works.
3. Persist source metadata required by Step 4 sentiment enrichment.

---

## Acceptance Criteria

1. At least two providers can be configured and ingested.
2. Duplicate story suppression works across providers.
3. Quota limits are enforced without full-pipeline failure.
4. Sentiment pipeline remains stable on partial provider outages.
5. New metadata fields are persisted and available to downstream nodes.

---

## Test Plan

1. Unit: adapter normalization for each provider.
2. Unit: canonicalization and dedup edge cases.
3. Integration: multi-provider ingestion happy path.
4. Integration: one-provider-fails fallback behavior.
5. Integration: quota exhaustion behavior.

Suggested commands:

```bash
uv run pytest tests/test_sentiment.py -v
uv run pytest tests/ --cov=alphawatch --cov-report=term-missing
```

---

## Rollout Plan

1. Enable second provider in staging only.
2. Compare ingest volume, duplicate rate, and error rates.
3. Tune quotas and dedup thresholds.
4. Promote to production with observability alerts enabled.

---

## Risks and Mitigations

1. Risk: Cost increase due to multiple providers.
   Mitigation: hard quotas and source prioritization order.
2. Risk: False-positive dedup removes unique stories.
   Mitigation: conservative matching and audit logs.
3. Risk: Schema drift from providers.
   Mitigation: adapter-level validation and fallback defaults.

---

## Deliverables

1. Multi-source adapter framework.
2. Cross-source dedup and quota logic.
3. Updated sentiment fetch integration.
4. Test coverage for multi-source resilience paths.
