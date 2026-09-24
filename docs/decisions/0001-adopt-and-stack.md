# ADR 0001 — Adopt and Extend OpenNotebook; Ratify Target Stack

- Status: Accepted
- Date: 2026-09-24
- Deciders: Project owner, architecture
- Supersedes: n/a

## Context

We are building a central enterprise information lake that ingests from many
enterprise systems (SharePoint, Confluence, SQL, Salesforce, file shares, REST
APIs) and lets users chat with it in natural language, receiving grounded answers
with citations.

An existing codebase (`OpenNotebook`) already implements a large portion of this
target. A code audit found it covers, in working form: a MinIO/S3 data lake with a
storage abstraction, a pluggable connector framework, semantic chunking, BGE
embeddings, a Qdrant vector store with ACL metadata, hybrid retrieval
(dense + BM25 + cross-encoder rerank), a FastAPI serving layer with SSE streaming
and grounded citations, structured JSON logging, OpenTelemetry, Prometheus/Grafana/
Loki, and a CI/CD pipeline with Helm/Terraform.

The audit also identified gaps: permission-aware retrieval exists but is not wired
into the serving path; enterprise connectors are limited to web + S3; ingestion is
not idempotent across syncs; there is no evaluation harness; and one boot-blocking
import defect.

## Decision

1. **Extend OpenNotebook. Do not rebuild from scratch.** Reuse the ingestion,
   storage, chunking, retrieval, serving, governance, observability, and deployment
   assets. Close gaps stage by stage.
2. **Keep Qdrant** as the vector store (rather than migrating to pgvector).
3. **Local-first, pluggable providers.** Keep Ollama + BGE as defaults and add
   provider interfaces so cloud models (OpenAI, Anthropic, Gemini) can be
   configured without changing call sites.
4. **Deploy to self-hosted / on-prem Kubernetes.** Existing Helm + Terraform GKE
   manifests are the starting point and will be adapted.
5. **Internal-only data.** No formal compliance regime (GDPR/HIPAA/SOC2) applies
   at this time; audit logging and PII controls are kept as defence-in-depth.
6. **Target scale:** 10k–1M documents, 25–500 users per deployment.

## Stack and tradeoffs

| Concern | Choice | Rationale | Tradeoff / Alternative |
|---|---|---|---|
| Language | Python 3.12 | Matches runtime image `python:3.12-slim` | Local machine currently has 3.11.9; install 3.12 (or relax `requires-python`) |
| API | FastAPI | Already used; async, Pydantic v2 strict models | — |
| Vector DB | Qdrant | Already integrated; native metadata filtering + hybrid | pgvector = one fewer service but a retrieval rewrite |
| Embeddings | BGE-small-en-v1.5, pluggable | Local, free, private; no data egress | Cloud (OpenAI v3-large) needs a provider adapter |
| LLM | Ollama default, pluggable | Private by default; provider abstraction allows GPT-4o/Claude/Gemini | Cloud providers require keys and egress policy |
| Orchestration | Hand-rolled pipeline (not LangChain/LlamaIndex) | Explicit, testable, no framework coupling; already works | LlamaIndex may be adopted selectively for connector parsing |
| Scheduling | Celery (+ beat) | Already present; sufficient for connector syncs | Airflow/Dagster only if complex DAGs emerge |
| Task queue | Celery + Redis | Already present | — |
| Storage | MinIO / S3-compatible | Already present; local fallback | — |
| Frontend | React + Vite | Already present; streaming + citations work | Migrate to Next.js only if SSR/OIDC server-side is required |
| Auth | JWT + bcrypt now; OIDC later | Works today; OIDC (Entra/Keycloak) added in Stage 7 | — |
| Deployment | Docker Compose (dev), Helm (on-prem K8s) | Already present | — |

## Monorepo structure (existing mapping)

The requested folder names map onto the existing layout. Renaming would break
imports, CI, and Docker contexts for no functional gain, so we keep the current
top-level layout and document the mapping:

| Requested | Existing | Contents |
|---|---|---|
| `/ingestion` | `backend/app/domain/connectors`, `backend/app/worker` | Connectors, Celery ingest tasks, extractors, chunker, embedder |
| `/serving` | `backend/app/api`, `backend/app/domain/chat`, `backend/app/domain/retrieval` | FastAPI routes, RAG orchestration, retrieval |
| `/shared` | `backend/app/core`, `backend/app/infrastructure` | Config, auth, audit, logging, metrics, DB/Qdrant/Redis/MinIO clients |
| `/infra` | `terraform/`, `helm/`, `docker-compose*.yml`, `.github/` | IaC, charts, CI/CD |
| `/frontend` | `frontend/` | React chat UI |

## Consequences

- The Stage 0–11 plan is re-scoped as a gap-closure plan against the existing repo
  (see `docs/plans/stage-plan.md`).
- Permission-aware retrieval must be wired before any multi-user (25–500 users)
  rollout; it is currently latent, not enforced.
- Provider pluggability (LLM + embeddings) is net-new work scheduled in Stage 6.
- Local Python must be 3.12 to match `requires-python` and the container image.

## Out of scope

- Formal compliance certification, multi-tenant data isolation beyond a single
  organisation, and cloud-managed deployment are out of scope for this phase.
