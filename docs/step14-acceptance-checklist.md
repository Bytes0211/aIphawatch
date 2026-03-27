# Step 14 Acceptance Checklist (Solo Operator)

## Scope
- Step 14: CI/CD pipeline + staging deployment
- Operating model: one-person team
- Excluded: mandatory human approval gates before production deploy
- Replacement: controlled production trigger (tag or manual dispatch), no reviewer dependency

## Definition of Done
Step 14 is complete only when every item below is true and verifiable in-repo.

---

## 1) CI quality gate runs on every PR

Target files:
- `README.md`
- `.github/workflows/ci.yml`

Acceptance criteria:
- PRs trigger CI automatically.
- CI includes backend and frontend quality checks:
  - `uv run pytest tests/`
  - `mypy alphawatch/`
  - `ruff check alphawatch/`
  - `npm test`
  - `npx tsc --noEmit`
- CI failure blocks merge (GitHub branch protection setting).
- README CI badge points to the actual CI workflow file.

Evidence to capture:
- Link to one passing PR run.
- Screenshot or note of required status checks in branch protection.

---

## 2) Deployable artifacts are built deterministically

Target files:
- `.github/workflows/build-artifacts.yml`
- `package.json`
- `pyproject.toml`
- `next.config.mjs`

Acceptance criteria:
- Backend artifact is built and pushed to ECR with immutable tag (commit SHA).
- Frontend build artifact is generated and retained by Actions artifacts.
- Build metadata maps artifact -> commit SHA.

Evidence to capture:
- ECR image tag containing commit SHA.
- Build job logs showing frontend artifact upload.

---

## 3) GitHub Actions uses OIDC (no long-lived cloud keys)

Target files:
- `.github/workflows/*.yml`
- `README.md`

Acceptance criteria:
- Workflows authenticate to AWS using OIDC role assumption.
- No static AWS access keys required for pipeline execution.
- Required secrets/variables are documented.

Evidence to capture:
- Workflow log lines proving role assumption.
- README section listing required repo/environment variables.

---

## 4) Staging deploy is automated end-to-end

Target files:
- `.github/workflows/deploy-staging.yml`
- `infra/environments/staging/main.tf`
- `infra/environments/staging/providers.tf`
- `infra/environments/staging/backend.tf`
- `infra/environments/staging/variables.tf`
- `infra/environments/staging/terraform.tfvars`

Acceptance criteria:
- Main branch merge triggers staging deploy workflow.
- Workflow runs Terraform init/validate/plan/apply for staging.
- ECS services roll to healthy state before workflow passes.
- Optional frontend static publish runs only when `DEPLOY_FRONTEND_STATIC=true`.
- Any deploy failure marks workflow failed.

Evidence to capture:
- One successful staging deploy run URL.
- Terraform/apply summary in workflow logs.

---

## 5) ECS rollout and health checks are enforced

Target files:
- `.github/workflows/deploy-staging.yml`
- `alphawatch/api/routers/health.py`

Acceptance criteria:
- Workflow waits for ECS service stability.
- Health endpoint check is executed post-rollout.
- Non-healthy rollout fails the pipeline.

Evidence to capture:
- Log lines for ECS wait/stability.
- Log lines for health probe response.

---

## 6) Smoke tests run after staging deploy

Target files:
- `.github/workflows/deploy-staging.yml`
- `tests/` (smoke scripts or curl-based checks from workflow)

Acceptance criteria:
- Smoke stage runs automatically after deploy success.
- Includes at least:
  - unauthenticated `/health`
  - one authenticated API endpoint
- Smoke failure fails the workflow.

Evidence to capture:
- Smoke step logs with pass/fail output.

---

## 7) Production release flow exists (no approvals)

Target files:
- `.github/workflows/release-prod.yml`
- `infra/environments/production/main.tf`
- `infra/environments/production/providers.tf`
- `infra/environments/production/backend.tf`
- `infra/environments/production/variables.tf`
- `infra/environments/production/terraform.tfvars`

Acceptance criteria:
- Production deploy is explicit trigger only (tag push or manual dispatch).
- No mandatory manual approval step.
- Production deploy promotes immutable artifact (no rebuild drift).

Evidence to capture:
- One production release run URL.
- Artifact tag in release logs.

---

## 8) Rollback is documented and executable

Target files:
- `README.md`
- `docs/project-status.md`
- `developer/developer-journal.md`

Acceptance criteria:
- Runbook includes exact rollback commands for:
  - app rollback (previous ECS task definition / image tag)
  - infra rollback strategy
- Single operator can execute rollback end-to-end from docs only.

Evidence to capture:
- Documented rollback section with tested commands.

---

## 9) Project tracking reflects Step 14 completion

Target files:
- `docs/project-status.md`
- `README.md`
- `developer/developer-journal.md`

Acceptance criteria:
- Step 14 checkbox marked complete.
- Pipeline status details updated to match real workflows.
- Journal entry added summarizing what was shipped and why.

Evidence to capture:
- Links to merged PR(s) and workflow runs.

---

## Quick verification commands (local)

```bash
uv run pytest tests/ -q
uv run mypy alphawatch/
uv run ruff check alphawatch/
npm test
npx tsc --noEmit
```

Note: deployment verification must come from GitHub Actions run logs and AWS service state.
