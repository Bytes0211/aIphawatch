# Phase 2 Step 2 — Runtime Foundations Rollout (Spec)

## Purpose

Define and implement runtime foundation changes needed before deeper Phase 2 feature delivery:

1. Complete financial provider abstraction rollout in runtime paths.
2. Move chat summarization off the synchronous request hot path.
3. Add validation and regression checks for correctness and latency.

---

## Scope

### In scope

1. Replace direct provider construction in ingestion/runtime call sites with `get_financial_data_provider()`.
2. Enforce config-driven provider selection via `Settings.financial_data_provider`.
3. Refactor chat summarization so `maybe_summarize` work does not block chat response path.
4. Add integration tests and runtime metrics around provider selection and summarization behavior.

### Out of scope

1. Adding a second financial provider implementation (this step is wiring plus contract hardening).
2. Step 3 multi-source news ingestion work.

---

## Current State

1. Provider abstraction exists in [alphawatch/services/financial.py](alphawatch/services/financial.py).
2. Config key exists in [alphawatch/config.py](alphawatch/config.py).
3. Chat summarization currently runs inline in `maybe_summarize` after `persist_turn` in [alphawatch/agents/nodes/chat.py](alphawatch/agents/nodes/chat.py).

---

## Target Architecture

### A. Provider wiring

1. Runtime entrypoints that need financial snapshots must resolve provider via factory.
2. No direct `AlphaVantageClient()` construction in runtime/graph node code paths.
3. Provider output normalization remains through the existing snapshot contract.

### B. Summarization off hot path

1. Request path returns streamed response without waiting for summarization.
2. Summarization work runs async via background task/worker pathway.
3. Failures in summarization do not fail user chat turn.
4. Summary freshness is eventually consistent and persisted to `ChatSession`.

---

## Implementation Plan

### Workstream 1: Provider factory rollout

1. Search and replace remaining concrete client usage.
2. Route call sites through `get_financial_data_provider()`.
3. Ensure provider resolution errors are explicit and observable.
4. Add one integration test for config-driven selection behavior.

### Workstream 2: Summarization decoupling

1. Introduce summary-needed signal after `persist_turn`.
2. Dispatch summarization to async execution path (worker/task/background queue).
3. Keep request path non-blocking and idempotent.
4. Persist summary updates with safe conflict handling.

### Workstream 3: Validation and metrics

1. Add metrics for summarization queue latency, success/failure rate, and staleness.
2. Add latency benchmark checks around threshold turns.
3. Validate no regressions in streaming behavior.

---

## Acceptance Criteria

1. No direct `AlphaVantageClient()` instantiation in runtime ingestion paths.
2. Provider selection is controlled by config and covered by integration tests.
3. Chat trigger-turn latency is not increased by summarization execution.
4. Summarization failures are isolated from user response success path.
5. Runtime metrics for provider failures and summarization health are emitted.

---

## Test Plan

1. Unit: provider factory and error paths.
2. Integration: config-based provider selection from runtime entrypoint.
3. Integration: chat turn continues when summarization task fails.
4. Regression: compare p95 chat latency before/after at summary threshold boundary.

Suggested commands:

```bash
uv run pytest tests/test_financial.py -v
uv run pytest tests/test_chat.py -v
uv run pytest tests/ --cov=alphawatch --cov-report=term-missing --cov-report=json:coverage.json --cov-fail-under=74
uv run python scripts/ci/coverage_gate.py coverage.json
```

---

## Rollout Plan

1. Deploy to staging with feature toggle or guarded path.
2. Validate latency and error metrics for 24h.
3. Promote to production with plan/apply workflow gates.
4. Monitor summarization queue depth and failure alerts.

---

## Risks and Mitigations

1. Risk: Summary stale window increases.
   Mitigation: bounded delay SLO and fallback to recent raw messages.
2. Risk: Task duplication.
   Mitigation: idempotency key per session/turn window.
3. Risk: Provider misconfiguration.
   Mitigation: startup/config validation plus clear error telemetry.

---

## Deliverables

1. Updated runtime code paths using provider factory.
2. Non-blocking summarization architecture implementation.
3. Tests proving config selection and non-blocking behavior.
4. Runtime metrics and alert thresholds documented.
