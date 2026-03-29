# Phase 2 Operations Runbook — News Source Ingestion

## Purpose

Operational procedures for running and troubleshooting multi-source news ingestion after Step 3 rollout.

---

## Daily Checks

1. Provider success rate by source.
2. Quota utilization per source.
3. Dedup ratio and merged article volume.
4. End-to-end sentiment pipeline completion rate.

---

## Key Metrics

1. `news_ingest_requests_total{provider,status}`
2. `news_ingest_quota_remaining{provider}`
3. `news_dedup_drop_total{provider}`
4. `news_articles_merged_total`
5. `sentiment_pipeline_failures_total`

---

## Alert Recommendations

1. Provider error rate > 10% over 15m.
2. Quota remaining < 10% before end of daily window.
3. Dedup drop ratio > 80% for 30m (possible canonicalization bug).
4. Sentiment pipeline failure rate > 5% for 15m.

---

## Common Failure Modes

### 1) Provider auth/rate failure

Symptoms:

1. Sudden increase in provider-specific 401/429/5xx.
2. Drop in merged article count.

Actions:

1. Validate API key/secret rotation state.
2. Confirm quota settings and current usage.
3. Temporarily lower provider priority and continue with remaining sources.

### 2) Over-aggressive dedup

Symptoms:

1. Merged article count collapses while provider pulls remain healthy.
2. Dedup ratio spikes unexpectedly.

Actions:

1. Inspect canonicalization output sample.
2. Switch to conservative fallback key.
3. Roll back recent dedup rule changes.

### 3) Pipeline partial failure propagation

Symptoms:

1. News ingest returns but sentiment records are missing.

Actions:

1. Verify `fetch_news` output shape in sentiment node logs.
2. Validate required metadata fields.
3. Re-run ingestion for impacted tickers after fix.

---

## Incident Response

1. Declare incident severity.
2. Capture failing provider, timeframe, and impacted tickers.
3. Apply fallback mode to maintain partial service.
4. Open incident entry in `developer/developer-journal.md`.
5. Post-incident: add regression test for root cause.

---

## Change Management

Before changing provider adapters, dedup logic, or quotas:

1. Run staging ingestion dry-run for representative tickers.
2. Compare dedup ratio against baseline.
3. Confirm alert thresholds still valid.
4. Update this runbook and Step 3 spec if behavior changes.

---

## Exit Criteria for Stable Operations

1. 7 consecutive days with no sev-1/sev-2 ingestion incidents.
2. Provider fallback behavior validated in at least one staged fault injection.
3. Alert noise rate acceptable (no sustained false positives).
4. On-call troubleshooting steps validated and current.
