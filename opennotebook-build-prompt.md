# OpenNotebook — Enhanced MVP Build Prompt

## Role

You are a Principal Software Engineer and AI Systems Architect.

Build a production-quality MVP of a NotebookLM-style application using ONLY
open-source technologies and locally hosted AI models.

The application will be deployed on Google Cloud Platform (GCP).

The goal is to allow users to create **Notebooks** (curated document collections),
upload sources, ask questions with grounded citations, stream answers in real time,
and maintain full conversational context — all without sending a single byte to a
proprietary AI provider.

---

## Product Name

```text
OpenNotebook
```

Tagline:

```text
Your private, open-source AI research assistant.
Understand anything. Keep everything local.
```

---

## Core UX Concept — Notebooks [ADDED]

A **Notebook** is the primary unit of organisation, mirroring NotebookLM.

```
User
 └── Notebooks (1…N)
      ├── Sources (documents, URLs, YouTube transcripts)
      ├── Chat sessions (tied to a notebook)
      └── Generated artifacts (summaries, study guides, FAQs)
```

Every feature is scoped to a Notebook. Users switch between notebooks via a
sidebar. Multiple notebooks can be open simultaneously in tabs.

---

## Feature List

### Phase 1 — MVP

1. Notebook creation, rename, and deletion
2. Source upload (PDF, DOCX, TXT, Markdown)
3. URL ingestion (scrape and chunk web pages) [ADDED]
4. YouTube transcript ingestion [ADDED]
5. Text extraction with page/section metadata
6. Semantic chunking (800 tokens, 100 overlap)
7. Local embedding generation (BGE-small-en-v1.5)
8. Hybrid retrieval (vector + BM25 + cross-encoder reranking) [CHANGED]
9. Streaming RAG answers via Server-Sent Events [ADDED]
10. Citations: document name, page, chunk ID — inline in streamed answer [CHANGED]
11. Conversation history (multiple sessions per notebook)
12. Source deletion and re-indexing
13. Full-text search across sources
14. Document summaries (executive, key findings, entities)
15. Model registry — swap LLM/embedding model via settings UI [ADDED]
16. Dead letter queue (DLQ) for failed processing jobs [ADDED]
17. Processing status dashboard with real-time progress [ADDED]
18. Export: chat session → Markdown or PDF [ADDED]

### Phase 2 — Post-MVP

19. Audio summaries (TTS via Coqui TTS)
20. Podcast-style dialogue generation
21. Multi-user workspaces with RBAC
22. Shared notebooks (read-only share links)
23. Knowledge graph visualisation (NetworkX + D3)
24. Graph RAG (entity-centric retrieval)
25. Agentic retrieval (multi-hop reasoning)
26. OCR for scanned PDFs (Tesseract)
27. Image understanding (LLaVA via Ollama)
28. Plugin system for custom extractors and chunkers [ADDED]

---

## Architecture

```
Browser
  │
  │  REST + Server-Sent Events (SSE)
  ▼
React + TypeScript (Vite)
  │
  │  HTTPS
  ▼
FastAPI (API Gateway)
  ├── Auth middleware (JWT + refresh tokens)
  ├── Rate limiting (slowapi)
  ├── Audit log
  └── OpenAPI 3.1 spec
  │
  ├─────────────────────────────────┐
  │                                 │
  ▼                                 ▼
Notebook Service              RAG Pipeline Service
(CRUD, indexing triggers)     (retrieval, generation, streaming)
  │                                 │
  ├── PostgreSQL                    ├── Qdrant (vectors)
  └── MinIO (source files)          ├── BM25 index (rank_bm25)
                                    ├── Cross-encoder reranker [ADDED]
                                    │   (BAAI/bge-reranker-base)
                                    └── Ollama (LLM streaming)
  │
  ▼
Worker Service (Celery + Redis)
  ├── Text extraction
  ├── Chunking
  ├── Batch embedding
  ├── Document indexing
  ├── Summarisation
  └── DLQ handler [ADDED]
  │
  ▼
Observability Stack
  ├── OpenTelemetry (traces + spans)
  ├── Prometheus (metrics)
  ├── Grafana (dashboards)
  └── Loki (log aggregation) [ADDED]
```

---

## Technology Stack

### Frontend

| Concern            | Library                        |
|--------------------|--------------------------------|
| Framework          | React 18 + TypeScript          |
| Build tool         | Vite 5                         |
| Styling            | Tailwind CSS v4                |
| State / async      | TanStack Query v5              |
| Routing            | TanStack Router                |
| Streaming          | EventSource API (native SSE)   |
| Markdown rendering | react-markdown + rehype-highlight |
| Command palette    | cmdk                           |
| Drag & drop upload | react-dropzone                 |
| Charts             | Recharts                       |

### Backend

| Concern            | Library                        |
|--------------------|--------------------------------|
| Framework          | FastAPI 0.111                  |
| ASGI server        | Uvicorn + Gunicorn             |
| ORM                | SQLAlchemy 2 (async)           |
| Migrations         | Alembic                        |
| Validation         | Pydantic v2                    |
| Auth               | python-jose (JWT)              |
| Rate limiting      | slowapi                        |
| HTTP client        | httpx (async)                  |
| Task queue         | Celery 5 + Redis               |
| Streaming          | FastAPI StreamingResponse      |

### AI / ML

| Concern            | Library / Model                |
|--------------------|--------------------------------|
| LLM inference      | Ollama (Llama 3 8B Instruct)   |
| Embeddings         | BAAI/bge-small-en-v1.5         |
| Reranker [ADDED]   | BAAI/bge-reranker-base         |
| Vector store       | Qdrant                         |
| BM25 [ADDED]       | rank_bm25                      |
| PDF extraction     | PyMuPDF                        |
| DOCX extraction    | python-docx                    |
| Web scraping       | trafilatura [ADDED]            |
| YouTube [ADDED]    | youtube-transcript-api         |

### Databases & Storage

- PostgreSQL 16
- Qdrant (latest)
- MinIO
- Redis 7

### Observability

- OpenTelemetry SDK (Python + JS)
- Prometheus
- Grafana + pre-built dashboards
- Loki (log aggregation) [ADDED]

### Infrastructure

- Docker + Docker Compose (local)
- Terraform (GCP)
- Helm charts (GKE) [ADDED]
- GitHub Actions CI/CD [ADDED]

---

## Functional Requirements

### Notebooks [ADDED]

```http
POST   /api/v1/notebooks
GET    /api/v1/notebooks
GET    /api/v1/notebooks/{id}
PATCH  /api/v1/notebooks/{id}
DELETE /api/v1/notebooks/{id}
```

Each notebook has:

```json
{
  "id": "uuid",
  "name": "My Research",
  "description": "...",
  "source_count": 5,
  "created_at": "...",
  "updated_at": "..."
}
```

---

### Source Upload

Supported formats:

```
PDF · DOCX · TXT · Markdown · URL · YouTube URL
```

Endpoint:

```http
POST /api/v1/notebooks/{notebook_id}/sources
```

Processing pipeline (async via Celery):

```
1. Store file in MinIO (or scrape URL)
2. Extract text + metadata
3. Chunk semantically
4. Generate embeddings (batched)
5. Upsert into Qdrant
6. Build BM25 index for notebook
7. Update source status → READY
```

Source statuses:

```
PENDING → EXTRACTING → CHUNKING → EMBEDDING → READY | FAILED
```

Expose real-time status via SSE:

```http
GET /api/v1/notebooks/{notebook_id}/sources/{source_id}/status
```

---

### Text Extraction

Extract while preserving:

- Page number
- Section heading hierarchy
- Document title and author (from metadata)
- Source URL (for web sources)
- Timestamp (for YouTube transcripts)

```python
# PDF
PyMuPDF (fitz)

# DOCX
python-docx

# Web
trafilatura (boilerplate removal + markdown extraction)

# YouTube
youtube-transcript-api (auto-generated + manual captions)
```

---

### Chunking

Strategy: **semantic chunking** with sliding window fallback.

Rules:

```
Target chunk size:   800 tokens
Overlap:             100 tokens
Minimum chunk size:  150 tokens
Split on:            paragraph > sentence > token boundary
```

Chunk metadata stored per chunk:

```json
{
  "chunk_id": "uuid",
  "source_id": "uuid",
  "notebook_id": "uuid",
  "text": "...",
  "token_count": 782,
  "page": 14,
  "section": "Related Work",
  "start_char": 4820,
  "end_char": 6201,
  "embedding_model": "BAAI/bge-small-en-v1.5"
}
```

---

### Embedding Pipeline

Model:

```
BAAI/bge-small-en-v1.5
Dimension: 384
```

Requirements:

- Local inference via sentence-transformers
- Batch size: 64 (configurable)
- Async Celery task with retry (max 3, exponential backoff)
- Embedding model version stored per chunk (enables re-indexing after model swap)

Store vectors in Qdrant with full chunk payload for zero-join retrieval.

---

### Retrieval Pipeline [CHANGED]

Implement **three-stage hybrid retrieval**:

#### Stage 1 — Parallel retrieval

```
a) Dense vector search (Qdrant cosine, top-k=20)
b) BM25 keyword search (rank_bm25, top-k=20)
```

#### Stage 2 — Score fusion

```
Reciprocal Rank Fusion (RRF) with k=60
rrf_score(d) = Σ 1 / (k + rank_i(d))
```

#### Stage 3 — Cross-encoder reranking [ADDED]

```
Model: BAAI/bge-reranker-base
Input: (query, chunk_text) pairs from top-20 fused results
Output: top-10 reranked chunks with confidence scores
```

Return the top 10 chunks with source metadata.

---

### RAG Pipeline + Streaming [CHANGED]

Stream the LLM response token-by-token via Server-Sent Events.

SSE event schema:

```
event: token
data: {"token": " the"}

event: citation
data: {"chunk_id": "abc", "source_name": "paper.pdf", "page": 12}

event: done
data: {"message_id": "uuid", "latency_ms": 1840}

event: error
data: {"code": "context_too_long", "message": "..."}
```

Prompt template:

```
<system>
You are a document research assistant for OpenNotebook.

Rules:
- Answer ONLY using the provided context.
- If the answer is not in the context, say exactly:
  "I could not find that information in this notebook's sources."
- Be concise. Cite sources inline using [Source N] notation.
- Never fabricate citations.
</system>

<context>
{context_blocks}
</context>

<conversation>
{history}
</conversation>

<question>
{question}
</question>
```

Each `context_block` includes chunk text, source name, and page number so the
model can produce inline citations naturally.

---

### Citations

Citations must appear inline in the streamed answer and in a structured
`sources` block appended after generation.

Example output:

```markdown
The transformer architecture relies on self-attention [Source 1] rather than
recurrence, enabling parallelisation during training [Source 2].

---
**Sources used**

1. attention_is_all_you_need.pdf — page 2
2. attention_is_all_you_need.pdf — page 4
```

Every citation exposes:

```json
{
  "chunk_id": "uuid",
  "source_name": "attention_is_all_you_need.pdf",
  "source_id": "uuid",
  "page": 2,
  "section": "Model Architecture",
  "relevance_score": 0.94
}
```

---

### Conversation Memory

Schema:

```sql
chat_sessions (
  id          UUID PRIMARY KEY,
  notebook_id UUID NOT NULL REFERENCES notebooks(id),
  title       TEXT,
  created_at  TIMESTAMPTZ,
  updated_at  TIMESTAMPTZ
)

messages (
  id              UUID PRIMARY KEY,
  session_id      UUID NOT NULL REFERENCES chat_sessions(id),
  role            TEXT CHECK (role IN ('user', 'assistant')),
  content         TEXT,
  citations       JSONB,
  retrieval_meta  JSONB,   -- scores, latencies, model used
  created_at      TIMESTAMPTZ
)
```

Context window management:

- Last N messages sent to LLM (N configurable, default 10)
- Token budget tracked — truncate oldest messages when approaching limit
- System prompt always included

---

### Summarisation [CHANGED]

```http
POST /api/v1/notebooks/{notebook_id}/sources/{source_id}/summary
```

Generate asynchronously. Return:

```json
{
  "executive_summary": "...",
  "key_findings": ["...", "..."],
  "important_entities": {
    "people": ["..."],
    "organisations": ["..."],
    "concepts": ["..."]
  },
  "suggested_questions": ["...", "...", "..."]
}
```

`suggested_questions` surfaces 3 questions the user might want to ask — seeded
into the chat input as quick prompts.

---

### Model Registry [ADDED]

Users can swap models without redeployment.

```http
GET  /api/v1/models
POST /api/v1/models/llm
POST /api/v1/models/embedding
```

Stored in settings table:

```json
{
  "llm_model": "llama3:8b-instruct",
  "embedding_model": "BAAI/bge-small-en-v1.5",
  "reranker_model": "BAAI/bge-reranker-base",
  "llm_temperature": 0.1,
  "llm_context_window": 8192,
  "max_retrieved_chunks": 10
}
```

If the embedding model changes, the system prompts the user to re-index affected
notebooks. Re-indexing runs as a background job and tracks progress via SSE.

---

### Export [ADDED]

```http
POST /api/v1/chat/{session_id}/export
Content-Type: application/json
{"format": "markdown" | "pdf"}
```

Export includes:

- Session title and date
- All messages with citations
- Source list with metadata

---

## API Design

### Notebooks

```http
POST   /api/v1/notebooks
GET    /api/v1/notebooks
GET    /api/v1/notebooks/{id}
PATCH  /api/v1/notebooks/{id}
DELETE /api/v1/notebooks/{id}
```

### Sources

```http
POST   /api/v1/notebooks/{id}/sources
GET    /api/v1/notebooks/{id}/sources
GET    /api/v1/notebooks/{id}/sources/{source_id}
DELETE /api/v1/notebooks/{id}/sources/{source_id}
POST   /api/v1/notebooks/{id}/sources/{source_id}/reindex
GET    /api/v1/notebooks/{id}/sources/{source_id}/status   (SSE)
POST   /api/v1/notebooks/{id}/sources/{source_id}/summary
```

### Chat

```http
POST /api/v1/notebooks/{id}/chat              (SSE streaming)
GET  /api/v1/notebooks/{id}/sessions
GET  /api/v1/sessions/{session_id}
GET  /api/v1/sessions/{session_id}/messages
POST /api/v1/sessions/{session_id}/export
DELETE /api/v1/sessions/{session_id}
```

### Search

```http
POST /api/v1/notebooks/{id}/search
```

### Models [ADDED]

```http
GET  /api/v1/models
POST /api/v1/models/llm
POST /api/v1/models/embedding
```

### System

```http
GET /api/v1/health
GET /api/v1/metrics          (Prometheus format)
GET /api/v1/jobs/{job_id}    (background job status)
```

All endpoints versioned under `/api/v1/`.
OpenAPI 3.1 spec auto-generated and served at `/api/docs`.

---

## Database Schema

### Migration strategy

- Alembic autogenerate for schema changes
- Migrations committed to `alembic/versions/`
- `make db-upgrade` / `make db-downgrade` commands

### Tables

```sql
users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
)

notebooks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  description TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
)

sources (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notebook_id      UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
  name             TEXT NOT NULL,
  source_type      TEXT NOT NULL CHECK (source_type IN ('pdf','docx','txt','md','url','youtube')),
  storage_path     TEXT,               -- MinIO object key
  source_url       TEXT,               -- for URL/YouTube sources
  status           TEXT NOT NULL DEFAULT 'PENDING',
  error_message    TEXT,
  page_count       INTEGER,
  chunk_count      INTEGER,
  embedding_model  TEXT,
  metadata         JSONB DEFAULT '{}',
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
)

source_summaries (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id           UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  executive_summary   TEXT,
  key_findings        JSONB,
  entities            JSONB,
  suggested_questions JSONB,
  created_at          TIMESTAMPTZ DEFAULT NOW()
)

chat_sessions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
  title       TEXT DEFAULT 'New chat',
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
)

messages (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id     UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role           TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content        TEXT NOT NULL,
  citations      JSONB DEFAULT '[]',
  retrieval_meta JSONB DEFAULT '{}',
  created_at     TIMESTAMPTZ DEFAULT NOW()
)

settings (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  llm_model       TEXT DEFAULT 'llama3:8b-instruct',
  embedding_model TEXT DEFAULT 'BAAI/bge-small-en-v1.5',
  reranker_model  TEXT DEFAULT 'BAAI/bge-reranker-base',
  llm_temperature NUMERIC DEFAULT 0.1,
  context_window  INTEGER DEFAULT 8192,
  max_chunks      INTEGER DEFAULT 10,
  updated_at      TIMESTAMPTZ DEFAULT NOW()
)
```

All tables include `created_at` and `updated_at` with trigger-based
auto-update for `updated_at`.

---

## Frontend Requirements [CHANGED]

### Pages

```
/                   → Landing / onboarding
/notebooks          → Notebook dashboard
/notebooks/:id      → Notebook workspace
/notebooks/:id/chat → Chat workspace
/settings           → Settings (model registry, account)
```

### Global UX Features [ADDED]

- **Command palette** (`⌘K`): search notebooks, sources, sessions, settings
- **Dark mode**: system-default with manual toggle
- **Keyboard shortcuts**: `N` new notebook, `U` upload, `/` focus chat input
- **Responsive layout**: mobile-friendly collapsed sidebar
- **Toast notifications**: job progress, errors, success

### Notebook Dashboard

Show:

- Notebook cards with source count, last active
- Create notebook button
- Notebook search

### Notebook Workspace

Split layout:

```
┌──────────────────┬────────────────────────────┐
│  Sources sidebar │  Main panel                │
│                  │                            │
│  • source list   │  Active: Chat | Summary    │
│  • add source    │                            │
│  • status badge  │                            │
└──────────────────┴────────────────────────────┘
```

### Chat Workspace [CHANGED]

Features:

- Streaming token display (character-by-character)
- Inline citation chips that expand on hover (show chunk excerpt)
- Session switcher sidebar
- Source filter (query only selected sources)
- Quick prompts from document summaries
- Regenerate last answer button
- Copy message to clipboard
- Export session button

### Source Library

Features:

- Upload via drag & drop or URL paste
- Real-time processing status with progress bar (SSE-driven)
- Source detail view: metadata, summary, suggested questions
- Re-index button (after model change)
- Delete with confirmation

### Settings Page [ADDED]

- LLM model selector (pulls available models from Ollama API)
- Embedding model selector
- Reranker toggle
- Temperature slider
- Context window size
- Account info

---

## Background Jobs

Celery worker with Redis broker and result backend.

### Task definitions

```python
@celery.task(bind=True, max_retries=3, default_retry_delay=30)
def process_source(self, source_id: str) -> None:
    # 1. Update status → EXTRACTING
    # 2. Extract text from storage
    # 3. Update status → CHUNKING
    # 4. Chunk text semantically
    # 5. Update status → EMBEDDING
    # 6. Batch embed chunks
    # 7. Upsert to Qdrant
    # 8. Update BM25 index
    # 9. Update status → READY
    # On failure: status → FAILED, log to DLQ

@celery.task
def generate_summary(source_id: str) -> None: ...

@celery.task
def reindex_notebook(notebook_id: str) -> None: ...

@celery.task
def handle_dlq(job_id: str, error: str) -> None: ...
```

### Dead Letter Queue [ADDED]

Failed tasks after max retries:

1. Log to `failed_jobs` table with full traceback
2. Expose in admin UI
3. Allow manual retry via API

```http
GET  /api/v1/jobs/failed
POST /api/v1/jobs/{job_id}/retry
```

### Flower dashboard [ADDED]

Expose Celery monitoring UI at `/flower` in development.

---

## Observability [CHANGED]

### Traces (OpenTelemetry)

Instrument:

```
FastAPI request lifecycle
Celery task lifecycle
Qdrant query
Ollama inference call
PostgreSQL queries (via SQLAlchemy instrumentation)
```

Export to Tempo (Grafana) via OTLP.

### Metrics (Prometheus)

```
opennotebook_api_request_duration_seconds{endpoint, method, status}
opennotebook_embedding_duration_seconds{batch_size, model}
opennotebook_llm_tokens_total{model, type}   # type: prompt|completion
opennotebook_llm_duration_seconds{model}
opennotebook_retrieval_duration_seconds{stage}  # dense|bm25|rerank
opennotebook_job_duration_seconds{task}
opennotebook_job_failures_total{task}
opennotebook_active_sources{notebook_id}
```

### Logs (Loki) [ADDED]

Structured JSON logs shipped to Loki via Promtail.

Fields on every log line:

```json
{
  "timestamp": "...",
  "level": "INFO",
  "service": "api|worker|rag",
  "trace_id": "...",
  "user_id": "...",
  "notebook_id": "...",
  "event": "retrieval_complete",
  "latency_ms": 142
}
```

### Grafana Dashboards [ADDED]

Pre-built dashboards committed to `grafana/dashboards/`:

- API overview (latency, error rate, request volume)
- RAG pipeline (retrieval, reranking, LLM latency breakdown)
- Worker overview (job throughput, failure rate, DLQ depth)
- Notebook activity (sources per notebook, chat volume)

---

## Security

```
JWT auth:         Access token (15 min) + refresh token (7 days)
Input validation: Pydantic v2 strict mode on all request bodies
File validation:  MIME type check + magic bytes check + size limit
Rate limiting:    Per-user via slowapi + Redis
Upload limits:    50 MB per file, 10 files per request
CORS:             Strict origin whitelist
Audit log:        All mutations logged to audit_log table
Password:         bcrypt (cost factor 12)
Secrets:          Environment variables, never committed
```

---

## Plugin Architecture [ADDED]

Make it easy for the community to extend OpenNotebook.

### Extractor plugin interface

```python
from abc import ABC, abstractmethod
from opennotebook.plugins import SourceExtractor, ExtractionResult

class MyExtractor(SourceExtractor):
    supported_types = ["application/x-my-format"]

    @abstractmethod
    async def extract(self, file_path: str) -> ExtractionResult:
        ...
```

Register via entry point in `pyproject.toml`:

```toml
[project.entry-points."opennotebook.extractors"]
my_format = "my_package:MyExtractor"
```

### Chunker plugin interface

```python
class MyChunker(Chunker):
    async def chunk(self, text: str, metadata: dict) -> list[Chunk]:
        ...
```

This allows the community to contribute:

- New file format extractors (EPUB, PPT, CSV, audio transcripts)
- Alternative chunking strategies (proposition chunking, semantic sentences)
- Custom embedding adapters (HuggingFace models not in default list)

---

## Project Structure

```
opennotebook/
├── .github/
│   └── workflows/
│       ├── ci.yml          # lint, test, build on PR
│       └── deploy.yml      # push to GKE on main merge [ADDED]
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── notebooks.py
│   │   │       ├── sources.py
│   │   │       ├── chat.py
│   │   │       ├── search.py
│   │   │       ├── models.py
│   │   │       └── health.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── auth.py
│   │   │   └── logging.py
│   │   ├── domain/
│   │   │   ├── notebooks/
│   │   │   ├── sources/
│   │   │   ├── chat/
│   │   │   └── retrieval/
│   │   ├── infrastructure/
│   │   │   ├── db/
│   │   │   ├── minio/
│   │   │   ├── qdrant/
│   │   │   ├── ollama/
│   │   │   └── redis/
│   │   ├── plugins/          [ADDED]
│   │   │   ├── base.py
│   │   │   ├── extractors/
│   │   │   └── chunkers/
│   │   └── worker/
│   │       ├── tasks/
│   │       └── dlq.py        [ADDED]
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/           # headless base components
│   │   │   ├── notebook/
│   │   │   ├── chat/
│   │   │   ├── source/
│   │   │   └── command/      # command palette [ADDED]
│   │   ├── hooks/
│   │   │   ├── useStream.ts  # SSE hook [ADDED]
│   │   │   └── useNotebook.ts
│   │   ├── pages/
│   │   ├── stores/
│   │   └── lib/
│   ├── tests/
│   └── Dockerfile
├── worker/
│   └── Dockerfile
├── grafana/
│   └── dashboards/           [ADDED]
├── helm/                     [ADDED]
│   └── opennotebook/
├── terraform/
│   ├── modules/
│   │   ├── gke/
│   │   ├── storage/
│   │   └── networking/
│   └── environments/
│       ├── local/
│       └── production/
├── docker-compose.yml
├── docker-compose.prod.yml   [ADDED]
├── Makefile                  [ADDED]
└── docs/
    ├── architecture.md
    ├── local-dev.md
    ├── production-deploy.md
    ├── contributing.md       [ADDED]
    └── plugin-guide.md       [ADDED]
```

---

## Developer Experience [ADDED]

### Makefile targets

```makefile
make dev          # start all services with hot reload
make test         # run backend + frontend tests
make lint         # ruff + mypy + eslint
make db-upgrade   # run pending Alembic migrations
make db-downgrade # rollback last migration
make seed         # populate with demo notebook + sources
make worker-logs  # tail Celery worker output
make flower       # open Celery Flower dashboard
make build        # build all Docker images
make push         # push to Artifact Registry
make deploy       # deploy to GKE via Helm
```

### Demo seeder [ADDED]

`make seed` loads a demo notebook with:

- 3 PDF sources (public domain research papers)
- Pre-generated summaries
- A sample conversation demonstrating citations

Useful for screenshots, demos, and CI visual regression tests.

### One-command local start

```bash
git clone https://github.com/your-org/opennotebook
cd opennotebook
cp .env.example .env
make dev
# → http://localhost:5173
```

No manual service configuration required. All AI models pulled by Ollama on
first run.

---

## CI/CD [ADDED]

### GitHub Actions — CI (`ci.yml`)

Triggers: pull_request to `main`

```
jobs:
  backend:
    - ruff check
    - mypy
    - pytest (unit + integration, with Postgres + Qdrant testcontainers)
    - coverage report (≥ 80% required)

  frontend:
    - eslint
    - tsc --noEmit
    - vitest
    - playwright e2e (against docker-compose)

  docker:
    - Build all images
    - Trivy vulnerability scan
```

### GitHub Actions — Deploy (`deploy.yml`)

Triggers: push to `main`

```
1. Build + tag Docker images
2. Push to Artifact Registry
3. helm upgrade --install opennotebook ./helm/opennotebook
4. kubectl rollout status deployment/opennotebook-api
5. Run smoke tests against staging
```

---

## Deployment

### Local (Docker Compose)

Services:

```yaml
services:
  api:       FastAPI backend
  worker:    Celery worker
  frontend:  React dev server (or Nginx in prod)
  postgres:  PostgreSQL 16
  qdrant:    Qdrant
  minio:     MinIO
  redis:     Redis 7
  ollama:    Ollama (GPU passthrough if available)
  flower:    Celery Flower (dev only)
  prometheus: metrics scraping
  grafana:   dashboards
  loki:      log aggregation
  promtail:  log shipping
```

### Production (GKE)

Terraform modules:

```
modules/gke/        → GKE Autopilot cluster
modules/storage/    → Cloud Storage (for MinIO alt), CloudSQL
modules/networking/ → VPC, Cloud Armor, Load Balancer
```

Helm chart packages all application services.

GPU node pool for Ollama (NVIDIA L4 or T4).

Horizontal pod autoscaling on the API and worker deployments.

---

## Testing

### Backend

```
pytest + pytest-asyncio
Factory Boy for test fixtures
Testcontainers for Postgres + Qdrant + Redis
Respx for mocking httpx calls to Ollama

Coverage target: ≥ 80% lines
```

Critical test paths:

- Full RAG pipeline (retrieval → rerank → generate)
- SSE streaming response
- Document processing pipeline (extract → chunk → embed)
- DLQ retry logic
- JWT auth (issue, refresh, revoke)

### Frontend

```
Vitest + React Testing Library
Playwright for E2E
MSW (Mock Service Worker) for API mocking including SSE streams
```

---

## Documentation

Commit all docs under `docs/`:

```
architecture.md       → System design, data flows, design decisions
local-dev.md          → Prerequisites, setup, common tasks
production-deploy.md  → GKE deployment walkthrough
contributing.md       → How to open issues, PRs, add plugins
plugin-guide.md       → How to write and publish an extractor plugin
api-reference.md      → Generated from OpenAPI spec
```

### README requirements [ADDED]

The root `README.md` must include:

- Animated demo GIF (record with `make seed && make dev`)
- One-command install section
- Architecture diagram (link to `docs/architecture.md`)
- Feature comparison table vs NotebookLM
- Roadmap section (phase 1 vs phase 2)
- Contributing and plugin links
- Star / sponsor badges

---

## Engineering Constraints

- No proprietary AI services
- No OpenAI, Anthropic, Google, or Cohere APIs
- All inference runs locally via Ollama
- All embeddings generated locally via sentence-transformers
- All components containerised
- Full local operation via `make dev`
- Deployable to GKE via Helm + Terraform

---

## Code Quality Standards

- Python: strict Pydantic v2, ruff, mypy strict mode
- TypeScript: strict mode, no `any`
- Repository pattern for all data access
- Dependency injection throughout (FastAPI `Depends`)
- Domain-driven design: domain, application, infrastructure layers
- Structured JSON logging on every service
- No secrets in code — all via environment variables
- Comprehensive docstrings on all public functions
- OpenAPI examples on every endpoint

---

## Phase 2 Stretch Goals

1. Audio summaries (Coqui TTS)
2. Podcast-style two-host dialogue generation
3. Multi-user workspaces with RBAC
4. Shared notebook links (read-only)
5. Knowledge graph (NetworkX → D3 visualisation)
6. Graph RAG (entity-centric retrieval)
7. Agentic multi-hop retrieval
8. OCR for scanned PDFs (Tesseract)
9. Image understanding (LLaVA via Ollama)
10. Community plugin registry

---

## Success Criteria

The MVP is complete when:

1. A user can create a notebook, upload 5 PDFs, and receive a cited answer
   within 10 seconds on a 16 GB RAM machine (no GPU)
2. Streaming appears within 500 ms of submitting a question
3. All unit tests pass with ≥ 80% coverage
4. `make dev` brings up all services in under 90 seconds on a cold start
5. `make deploy` successfully deploys to a GKE cluster
6. The Grafana dashboard shows latency for all pipeline stages

Build this as the open-source alternative to NotebookLM that the community
has been waiting for.
