# Phase 2 Step 1 — Migration Drill Journal Entry Template

Use this template in `developer/developer-journal.md` after running the migration drill.

## Attempted Evidence (2026-03-29)

- Local/default DB check command (`uv run alembic current`) failed with:
  - `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "alphawatch"`
- Staging secret lookup succeeded:
  - `alphawatch/staging/db-password`
- Staging direct connectivity check from current host failed:
  - `psql ... host=alphawatch-staging-db.cw7zu0bmpcj3.us-east-1.rds.amazonaws.com ...`
  - Error: `timeout expired`
- Local container fallback unavailable:
  - `docker` command not installed on current host

## Successful Drill Evidence (Fill In)

### YYYY-MM-DD — Feature — Phase 2 Step 1 Migration Safety Drill Executed

**Phase:** Phase 2 — Foundations + Intelligence Expansion
**Branch:** main
**Environment:** staging
**Executed by:** [name]
**Execution location:** [CodeBuild in VPC / bastion / ECS task / CI runner in VPC]

**Commands used:**

1. Backup:
   - [exact pg_dump command]
2. Pre-migration revision check:
   - [exact psql revision query]
3. Rollback rehearsal:
   - [exact alembic downgrade command]
4. Post-rollback smoke:
   - [exact smoke query command]
5. Restore forward state:
   - [exact alembic upgrade head command]
6. Post-upgrade smoke:
   - [exact smoke query command]

**Outcome summary:**

- Backup success: yes/no
- Downgrade success: yes/no
- Upgrade success: yes/no
- Smoke checks after downgrade: pass/fail
- Smoke checks after upgrade: pass/fail

**Artifacts:**

- Backup file path: [path]
- Execution log path: [path]
- Optional CI job URL: [url]
- Optional CodeBuild build ID / CloudWatch log group: [id or log group]

**Notes:**

- [anything unusual observed]
