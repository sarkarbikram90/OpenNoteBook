# OpenNotebook — Agent Context

## Spec Reference
Full spec: `opennotebook-build-prompt.md` (read this for any domain you're building)

## Stack (quick ref)
- **Backend:** FastAPI + SQLAlchemy 2 async + Celery / Cloud Run HTTP Worker + Redis + Rust `PyO3` (`opennotebook_core`)
- **Frontend:** React 19 + TypeScript + Vite + TanStack Query + Tailwind v4
- **Databases & Storage:** PostgreSQL 16 + `pgvector` (or Qdrant) + Google Cloud Storage (V4 Signed URLs + Pub/Sub) / MinIO / S3 / Local
- **AI & RAG:** Ollama / Gemini / OpenAI / Anthropic + Vertex AI `text-embedding-004` or `BAAI/bge-small-en-v1.5` + `BAAI/bge-reranker-base` + Gemini Vision / Document AI / Tesseract OCR
- **Infrastructure:**
  - Local Dev: Docker Compose (`docker-compose.yml`, `docker-compose.gcs.yml`)
  - Cloud Production: **Google Cloud Run** (`opennotebook-api`, `opennotebook-worker`, `opennotebook-frontend`, `opennotebook-migrate` Job)
  - Container Registry: **Google Artifact Registry** (`opennotebook`)
  - CI/CD & Deploy: GitHub Actions (`.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `.github/workflows/eval.yml`) with **Workload Identity Federation (WIF)**
  - IaC / On-Prem: Terraform (`terraform/modules/cloudrun/`, `terraform/modules/gke/`, `terraform/modules/storage/`) + Helm (`helm/opennotebook/`)

## Architecture Layers (Backend)
- `app/api/v1/`       → route handlers only, thin
- `app/domain/`       → business logic, core RAG, connectors, governance, no framework coupling
- `app/infrastructure/` → DB, pgvector, Qdrant, GCS, Pub/Sub, MinIO, Redis, Vertex AI, Vision, Rust bridge
- `app/worker/`       → Celery tasks (`tasks/`) + Cloud Run HTTP worker (`http_worker.py`)
- `rust/`             → Compiled Rust `PyO3` extension (`opennotebook_core`: DFA PII, UAX #29 chunking, cached BM25)

## Non-negotiables
- All chat responses stream via SSE (Server-Sent Events)
- Repository pattern everywhere (no raw DB queries in routes)
- Pydantic v2 strict mode on request/response models
- Structured JSON logging on every service
- Zero secrets committed to the repository (managed via WIF, GitHub Secrets, and Secret Manager; fail-closed in production)

## Deployment Architecture (GCP Cloud Run)
- **Target Project / Region:** Configured via GitHub Secrets (`GCP_PROJECT_ID`, `GCP_REGION`; defaults to `gen-lang-client-0295924868` / `asia-southeast1`)
- **Artifact Registry:** `${GAR_LOCATION}/${PROJECT_ID}/opennotebook`
- **Services & Jobs:**
  - `opennotebook-migrate`: Cloud Run Job executing `alembic upgrade head` prior to API rollout.
  - `opennotebook-worker`: Dedicated Cloud Run HTTP ingestion worker (`uvicorn app.worker.http_worker:app`) receiving Pub/Sub `OBJECT_FINALIZE` pushes and internal API task dispatches.
  - `opennotebook-api`: FastAPI backend container running on `$PORT` with `--no-cpu-throttling` and `WORKER_HTTP_URL` wired to `opennotebook-worker`.
  - `opennotebook-frontend`: Nginx reverse proxy serving the React SPA bundle and proxying `/api/` to `opennotebook-api`.
- **Authentication:** Workload Identity Federation (`WIF_PROVIDER`) keyless authentication.

## Build Status
- [x] Phase 1: Scaffold + Docker Compose + Core RAG + Streaming + Observability + CI/CD
- [x] Phase 2a: GCS Signed URLs + Pub/Sub Ingestion + Vertex AI Embeddings + `pgvector` + Gemini Vision/Document AI
- [x] Phase 2b: Rust `PyO3` Data-Plane Accelerator (`opennotebook_core`)
- [x] Phase 2c: Cloud Run Hardening (Dedicated HTTP Worker, Alembic Migration Job, Fail-Closed Secrets, Cloud Run Terraform Module)
- [ ] Phase 2d: Frontend Parity (Connectors Management, Workspaces/RBAC & ACL Sharing, Jobs/Eval Dashboard)
- [ ] Phase 2e: Flagship Multimodal Intelligence (Audio Overviews & Interactive Knowledge Graph / GraphRAG)
