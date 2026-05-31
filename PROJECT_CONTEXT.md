# OpenNotebook — Agent Context

## Spec reference
Full spec: `opennotebook-build-prompt.md` (read this for any domain you're building)

## Stack (quick ref)
- Backend: FastAPI + SQLAlchemy 2 async + Celery + Redis
- Frontend: React 18 + TypeScript + Vite + TanStack Query + Tailwind v4
- DBs: PostgreSQL 16 + Qdrant + MinIO
- AI: Ollama + BGE-small-en-v1.5 + BGE-reranker-base
- Infra: Docker Compose (local) + GKE + Helm + Terraform

## Architecture layers (backend)
app/api/v1/       → route handlers only, thin
app/domain/       → business logic, no framework imports
app/infrastructure/ → DB, Qdrant, MinIO, Ollama clients
app/worker/tasks/ → Celery tasks

## Non-negotiables
- All responses stream via SSE
- Repository pattern everywhere (no raw DB calls in routes)
- Pydantic v2 strict mode on all request/response models
- Structured JSON logging on every service
- No secrets in code

## Build status (update this as phases complete)
- [x] Phase 1: Scaffold + Docker Compose
- [x] Phase 2: DB schema + migrations
- [x] Phase 3: Source processing pipeline
- [ ] Phase 4: RAG pipeline + streaming
- [ ] Phase 5: Frontend
- [ ] Phase 6: Observability + CI/CD