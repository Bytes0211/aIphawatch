# AIphaWatch

![Phase 1](https://img.shields.io/badge/phase-1%20MVP-blue?style=flat-square)
![Status](https://img.shields.io/badge/status-in%20progress-yellow?style=flat-square)
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

## Features

- **Analyst Briefs** — 8-section AI-generated briefs (snapshot, what changed, risk flags, sentiment, executive summary) via LangGraph + AWS Bedrock
- **RAG Chat** — Multi-turn conversational interface grounded in real source data, streamed via SSE with inline citations
- **Watchlist Dashboard** — Monday-morning digest sorted by most material changes across your tracked companies
- **Automated Ingestion** — SEC EDGAR filings, financial snapshots (Alpha Vantage / Polygon), and news (NewsAPI / Tavily) ingested on schedule via Celery
- **Multi-Tenant** — Tenant isolation enforced at the repository layer with PostgreSQL RLS as defense-in-depth
- **Citation-Backed** — Every claim in the executive summary traces to a retrieved source chunk

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

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended for environment management)
- Node.js 20+
- AWS CLI configured with appropriate credentials
- Terraform 1.6+

### Backend

```bash
# Install dependencies
uv sync

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

## Testing

```bash
# Backend tests (178 passing)
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

## Project Status

| Phase | Status | Description |
|---|---|---|
| Phase 1 — MVP | 🔧 In Progress | Auth, watchlist, EDGAR ingestion, financial API, news, briefs, chat, dashboard, infra |
| Phase 2 — Intelligence | ⏳ Planned | Full news depth, sentiment enrichment, risk flags, document upload, competitor lookup |
| Phase 3 — SaaS Hardening | ⏳ Planned | Tenant branding, alerts, admin panel, bulk import, brief export, usage tracking |
| Phase 4 — Scale & Polish | ⏳ Planned | Earnings transcripts, watchlist sharing, scheduled briefs, comparison views, audit log |

## Documentation

- [`docs/PRD-AIphaWatch-2026-03-25.md`](docs/PRD-AIphaWatch-2026-03-25.md) — Product requirements
- [`docs/AIphaWatch-TechnicalSpec.md`](docs/AIphaWatch-TechnicalSpec.md) — Technical specification
- [`docs/project-status.md`](docs/project-status.md) — Project status and phase tracking
- [`AGENTS.md`](AGENTS.md) — AI agent guidance and architecture reference
- [`developer/developer-journal.md`](developer/developer-journal.md) — Development log

## License

[MIT](LICENSE)
