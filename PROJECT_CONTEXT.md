# OpenNotebook — Agent Context

## Spec Reference
Full spec: `opennotebook-build-prompt.md` (read this for any domain you're building)

## Stack (quick ref)
- **Backend:** FastAPI + SQLAlchemy 2 async + Celery + Redis + psycopg2-binary
- **Frontend:** React 19 + TypeScript + Vite + TanStack Query + Tailwind v4
- **Databases & Storage:** PostgreSQL 16 + Qdrant (Vector DB) + MinIO / S3
- **AI & RAG:** Ollama + BGE-small-en-v1.5 + BGE-reranker-base (pluggable LLM/Embeddings)
- **Infrastructure:**
  - Local Dev: Docker Compose (`docker-compose.yml`)
  - Cloud Production: **Google Cloud Run** (`opennotebook-api`, `opennotebook-frontend`)
  - Container Registry: **Google Artifact Registry** (`opennotebook` in `us-central1`)
  - CI/CD & Deploy: GitHub Actions (`.github/workflows/deploy.yml`) with **Workload Identity Federation (WIF)**
  - Alternative / On-Prem: Kubernetes + Helm (`helm/opennotebook/`) + Terraform (`terraform/`)

## Architecture Layers (Backend)
- `app/api/v1/`       → route handlers only, thin
- `app/domain/`       → business logic, core RAG, connectors, no framework coupling
- `app/infrastructure/` → DB, Qdrant, MinIO, Redis, Ollama clients
- `app/worker/tasks/` → Celery background processing tasks

## Non-negotiables
- All chat responses stream via SSE (Server-Sent Events)
- Repository pattern everywhere (no raw DB queries in routes)
- Pydantic v2 strict mode on request/response models
- Structured JSON logging on every service
- Zero secrets committed to the repository (managed via WIF and GitHub Secrets)

## Deployment Architecture (GCP Cloud Run)
- **Target Project:** `founders-club-507318`
- **Region:** `us-central1`
- **Artifact Registry:** `us-central1-docker.pkg.dev/founders-club-507318/opennotebook`
- **Services:**
  - `opennotebook-api`: FastAPI backend container running on port `$PORT` (Uvicorn).
  - `opennotebook-frontend`: Nginx reverse proxy serving the React SPA bundle and proxying `/api/` to `opennotebook-api` with `proxy_ssl_server_name on;` and dynamic `$PORT` / `BACKEND_URL` resolution.
- **Authentication:** Workload Identity Federation (`WIF_PROVIDER`) keyless authentication using service account `opennotebook-deployer@founders-club-507318.iam.gserviceaccount.com`.
- **Required IAM Roles:**
  - `roles/run.admin` (Cloud Run Admin)
  - `roles/iam.serviceAccountUser` (Service Account User)
  - `roles/artifactregistry.writer` & `roles/artifactregistry.admin` (Artifact Registry upload & management)

## Build Status
- [x] Phase 1: Scaffold + Docker Compose
- [x] Phase 2: DB schema + migrations
- [x] Phase 3: Source processing pipeline
- [x] Phase 4: RAG pipeline + streaming
- [x] Phase 5: Frontend React UI
- [x] Phase 6: Observability + CI/CD
- [x] Phase 7: Migration to GCP Cloud Run with Workload Identity Federation