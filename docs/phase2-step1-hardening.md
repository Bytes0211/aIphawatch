# Phase 2 Step 1 — Platform Hardening Baseline Runbook

Execution checklist for the pre-Phase 2 hardening baseline.

## Execution Status (as of 2026-03-29)

| Deliverable | Status | Evidence |
| --- | --- | --- |
| IAM least-privilege validation | COMPLETE | Staging run + production plan-only run + policy detach recorded below |
| Reproducible build locks | COMPLETE | Enforced in CI (`uv sync --frozen`, `npm ci`, lockfile checks) |
| CI quality gates | COMPLETE | `--cov-fail-under=74` and `scripts/ci/coverage_gate.py` |
| Deploy guardrails validation | COMPLETE | `Deploy Staging` and `Release Production(plan_only=true)` succeeded |
| Observability baseline verification | PENDING | Targets documented; alert wiring verification still required |
| Migration safety drill | PENDING | Drill checklist defined; execution evidence not yet logged |
| Docs/runbook freeze | COMPLETE | Phase 2 Step 1/2/3 docs published under `docs/` |

Execution evidence update (2026-03-29):

- Observability verification command run: `aws --no-cli-pager cloudwatch describe-alarms ...`
- Verified production alarms found for `alphawatch-production`: ECS target-tracking CPU autoscaling alarms only
  - `TargetTracking-service/alphawatch-production/alphawatch-production-api-AlarmHigh-...`
  - `TargetTracking-service/alphawatch-production/alphawatch-production-api-AlarmLow-...`
  - `TargetTracking-service/alphawatch-production/alphawatch-production-worker-AlarmHigh-...`
  - `TargetTracking-service/alphawatch-production/alphawatch-production-worker-AlarmLow-...`
- No verified production alerts found yet for Step 1 required signals:
  - Chat latency P95
  - API 5xx rate (alphawatch production)
  - Chunk cache hit rate
  - Financial provider failure rate

- Migration drill execution attempts:
  - `uv run alembic current` failed against local-default config with `asyncpg.exceptions.InvalidPasswordError` for user `alphawatch`
  - Staging credential retrieval succeeded from Secrets Manager (`alphawatch/staging/db-password`)
  - Direct staging connectivity check failed from this host:
    - `psql ... host=alphawatch-staging-db.cw7zu0bmpcj3.us-east-1.rds.amazonaws.com ...` -> `timeout expired`
  - Local container fallback unavailable: `docker` not installed in current execution environment
- Outcome: migration drill cannot be executed from current host due network reachability constraints to private RDS endpoint.

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

Validation evidence recorded on 2026-03-29:

- `Deploy Staging` manual run succeeded: [Run 23709307521](https://github.com/Bytes0211/aIphawatch/actions/runs/23709307521)
- `Release Production` plan-only run succeeded: [Run 23709307896](https://github.com/Bytes0211/aIphawatch/actions/runs/23709307896)
- `PowerUserAccess` detached from `alphawatch-github-production`
- Remaining managed policies after detach: `AmazonEC2ContainerRegistryPowerUser`, `AmazonECS_FullAccess`, `AmazonS3FullAccess`

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

Verification required for Step 1 closure:

1. Confirm each alert exists in the monitoring system and is enabled for production.
2. Confirm routing destination for each alert (pager/Slack/ticket) and on-call ownership.
3. Confirm each alert has a dashboard link and runbook link attached.
4. Record the alert IDs/URLs and verification timestamp in `developer/developer-journal.md`.

Suggested evidence template:

```text
Observability verification timestamp:
Verified by:

Alert inventory:
- Chat latency P95: <alert-id-or-url>
- API 5xx rate: <alert-id-or-url>
- Chunk cache hit rate: <alert-id-or-url>
- Provider failure rate: <alert-id-or-url>

Routing destination and owner:
- <destination> / <owner>
```

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

Evidence template:

```text
Migration drill date:
Environment:
Executed by:

Commands:
1) <backup command>
2) <migration command>
3) <smoke query command>
4) <rollback command>
5) <post-rollback smoke query command>

Outcome summary:
- Backup success: yes/no
- Migration success: yes/no
- Rollback success: yes/no
- Smoke queries after rollback: pass/fail
- Notes:
```

---

## Completion Criteria

Step 1 is complete when all are true:

- IAM least-privilege validated with staging full deploy + production plan-only run.
- CI quality gates are active and green.
- Reproducible lock checks pass in CI.
- Observability baseline and alert targets are documented and configured.
- Migration safety drill completed and logged.
- Phase 2 docs/runbooks updated and frozen.

Current status as of 2026-03-29:

- Completed: IAM least-privilege validation, CI quality gates, reproducible lock checks, and Phase 2 runbook/spec documentation.
- Still pending for full Step 1 closure: observability alert configuration verification and one logged migration safety drill.

## Completion Record

Mark Step 1 complete only when all items above are complete.

- Final status: IN PROGRESS
- Remaining blockers:
  - Observability: required production alerts for Step 1 target signals are not yet verified as provisioned.
  - Migration drill: no reachable execution path from current host to staging/private RDS endpoint, and no local Docker fallback.
- Target closeout update location:
  - `docs/project-status.md`
  - `developer/developer-journal.md`

### Unblock Plan

1. Provision or confirm production alarms for all Step 1 required signals (chat P95, API 5xx, cache hit rate, provider failure rate).
2. Attach each alarm URL/ID, owner, and destination route (pager/Slack/ticket) in `developer/developer-journal.md`.
3. Run migration safety drill in a reachable environment (staging DB or local containerized DB).
4. Preferred execution location for the migration drill: VPC-attached CodeBuild project triggered manually from GitHub Actions.
5. Log backup, migrate, rollback, and post-rollback smoke evidence in `developer/developer-journal.md`.

### Ready-to-run Artifacts

- Migration drill script: `scripts/ops/migration_safety_drill.sh`
- Journal entry template: `docs/phase2-step1-migration-journal-template.md`
- Buildspec for VPC-attached runner: `buildspecs/migration-safety-drill.yml`
- Manual trigger workflow: `.github/workflows/run-staging-migration-drill.yml`

Preferred execution path:

1. Set `migration_drill_github_connection_arn` in `infra/environments/staging/terraform.tfvars`.
2. Apply staging Terraform so the `alphawatch-staging-migration-drill` CodeBuild project is created in the staging private subnets.
3. Run the `Run Staging Migration Drill` workflow from GitHub Actions.

Example execution (from a VPC-reachable host):

```bash
scripts/ops/migration_safety_drill.sh \
  --db-host alphawatch-staging-db.cw7zu0bmpcj3.us-east-1.rds.amazonaws.com \
  --db-port 5432 \
  --db-name alphawatch \
  --db-user alphawatch \
  --db-password-secret alphawatch/staging/db-password \
  --aws-region us-east-1
```
