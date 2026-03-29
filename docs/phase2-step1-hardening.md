# Phase 2 Step 1 — Platform Hardening Baseline Runbook

Execution checklist for the pre-Phase 2 hardening baseline.

---

## Scope

This runbook covers Step 1 deliverables:

1. Remove temporary broad production IAM access and validate least privilege.
2. Verify reproducible dependency locks for backend and frontend.
3. Enable CI quality gates (total + critical-path coverage).
4. Establish baseline observability metrics and alert thresholds.
5. Run one migration safety drill (backup, restore, rollback rehearsal).
6. Freeze docs/runbooks for Phase 2 start.

---

## 1. IAM Least-Privilege Validation

Use `developer/runbooks/policy_validation.md` for policy content and trust checks.

Required end-state:

- `PowerUserAccess` is detached from `alphawatch-github-production`.
- Staging deploy workflow succeeds.
- Production plan-only workflow succeeds.

Verify attached managed policies:

```bash
aws iam list-attached-role-policies \
  --role-name alphawatch-github-production \
  --query 'AttachedPolicies[].{Name:PolicyName,Arn:PolicyArn}' \
  --output table
```

If temporary broad access still exists:

```bash
aws iam detach-role-policy \
  --role-name alphawatch-github-production \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
```

---

## 2. Reproducible Build Locks

Backend lock check:

```bash
test -f uv.lock
uv sync --frozen --all-groups
```

Frontend lock check:

```bash
test -f package-lock.json
npm ci
```

CI enforces lockfile presence and frozen dependency resolution.

---

## 3. CI Quality Gates

CI now enforces:

- Total backend coverage floor via `--cov-fail-under=74`
- Critical-path coverage thresholds via `scripts/ci/coverage_gate.py`

Critical-path thresholds:

- `alphawatch/agents/nodes/chat.py`: >= 90%
- `alphawatch/agents/nodes/brief.py`: >= 90%
- `alphawatch/services/financial.py`: >= 70%

Local validation command:

```bash
uv run pytest tests/ \
  --cov=alphawatch \
  --cov-report=term-missing \
  --cov-report=json:coverage.json \
  --cov-fail-under=74
uv run python scripts/ci/coverage_gate.py coverage.json
```

---

## 4. Deploy Guardrails Validation

### Staging (full deploy)

Run `Deploy Staging` from latest `main` and verify:

- Terraform apply succeeds
- ECS API + worker wait steps succeed
- Smoke tests pass (`/health`, auth 401 on `/api/watchlist`)

### Production (plan-only)

Run `Release Production` with `workflow_dispatch` input:

- `plan_only=true`

Expected behavior:

- Terraform plan runs successfully
- Apply, rollout wait, and smoke-test steps are skipped

---

## 5. Baseline Observability Targets

Track and alert on these metrics before Phase 2 feature rollout:

1. Brief generation latency (P95)
2. Chat response latency (P95)
3. API error rate (5xx)
4. Chunk cache hit rate
5. Financial provider failure rate

Initial alert guidelines:

- P95 chat response > 15s for 15m
- API 5xx rate > 2% for 10m
- Chunk cache hit rate < 50% for 60m
- Provider failure rate > 5% for 15m

---

## 6. Migration Safety Drill

Run once before introducing new Phase 2 schema changes.

Checklist:

1. Snapshot/backup current database.
2. Apply latest migration in staging.
3. Execute representative smoke queries.
4. Rehearse rollback to prior schema state.
5. Re-run smoke queries after rollback.
6. Record timings and failure points.

Store evidence in `developer/developer-journal.md` with date, commands used, and outcomes.

---

## Completion Criteria

Step 1 is complete when all are true:

- IAM least-privilege validated with staging full deploy + production plan-only run.
- CI quality gates are active and green.
- Reproducible lock checks pass in CI.
- Observability baseline and alert targets are documented and configured.
- Migration safety drill completed and logged.
- Phase 2 docs/runbooks updated and frozen.
