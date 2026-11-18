<p align="center">
  <h1 align="center">📓 OpenNotebook</h1>
  <p align="center">
    <strong>Your private, open-source AI research assistant & enterprise RAG platform.</strong><br>
    Ingest documents, run hybrid search, and stream grounded answers with inline citations — 100% local by default, cloud-ready when you need it.
  </p>
</p>

<p align="center">
  <a href="https://github.com/sarkarbikram90/OpenNoteBook/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/sarkarbikram90/OpenNoteBook/ci.yml?branch=main&label=CI&style=flat-square" alt="CI Status">
  </a>
  <a href="https://github.com/sarkarbikram90/OpenNoteBook/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/sarkarbikram90/OpenNoteBook?style=flat-square" alt="License">
  </a>
  <a href="https://github.com/sarkarbikram90/OpenNoteBook/stargazers">
    <img src="https://img.shields.io/github/stars/sarkarbikram90/OpenNoteBook?style=flat-square" alt="Stars">
  </a>
  <a href="https://github.com/sarkarbikram90/OpenNoteBook/issues">
    <img src="https://img.shields.io/github/issues/sarkarbikram90/OpenNoteBook?style=flat-square" alt="Issues">
  </a>
  <a href="https://github.com/sarkarbikram90/OpenNoteBook/pulls">
    <img src="https://img.shields.io/github/issues-pr/sarkarbikram90/OpenNoteBook?style=flat-square" alt="PRs">
  </a>
</p>

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-key-features">Key Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-configuration">Configuration</a> •
  <a href="#-development--testing">Development</a> •
  <a href="#-deployment">Deployment</a> •
  <a href="#-roadmap">Roadmap</a>
</p>

---

## 📖 Overview

**OpenNotebook** is an open-source, privacy-first alternative to Google's NotebookLM designed for researchers, engineers, and enterprise teams. It transforms unstructured documents, web pages, images, and enterprise data sources into interactive, queryable notebooks.

By default, every stage of the pipeline—document parsing, OCR, PII redaction, semantic chunking, BGE vector embedding, cross-encoder reranking, and LLM inference via Ollama—runs **entirely on your infrastructure with zero data egress**. When cloud scale or proprietary frontier models are needed, OpenNotebook cleanly switches between local models and OpenAI, Anthropic, or Google Gemini, and deploys seamlessly to **Google Cloud Run** or **Kubernetes**.

### How OpenNotebook Compares

| Capability | OpenNotebook | NotebookLM |
|------------|:------------:|:----------:|
| **100% Local / Air-Gapped Execution** | ✅ | ❌ |
| **Open Source (MIT)** | ✅ | ❌ |
| **Pluggable LLMs** (Ollama, OpenAI, Anthropic, Gemini) | ✅ | ❌ |
| **Pluggable Object Storage** (Local, GCS Signed URLs + Pub/Sub, S3, MinIO) | ✅ | ❌ |
| **Pluggable Vector Databases** (PostgreSQL + `pgvector` & Qdrant) | ✅ | ❌ |
| **Hybrid Retrieval** (Dense Vector + Inverted-Index BM25 + Cross-Encoder Reranking) | ✅ | — |
| **Rust `PyO3` Data-Plane Acceleration** (`opennotebook_core`: DFA PII, UAX#29 Chunker, BM25) | ✅ | — |
| **Real-Time SSE Streaming & Grounded Inline Citations** | ✅ | ✅ |
| **Automated PII Redaction & Security Guardrails** | ✅ | ❌ |
| **Enterprise Connectors & ACL Filtering** | ✅ | ❌ |
| **Extensible Extractor & Chunker Plugin System** | ✅ | ❌ |
| **Built-In RAG Evaluation & Observability Stack** | ✅ | ❌ |

---

## ✨ Key Features

- **Multi-Format Document Ingestion, OCR & Multimodal Vision**
  - Upload **PDFs** (`PyMuPDF`), **Word documents** (`.docx`), **Markdown**, **Plain Text**, **Web URLs** (`trafilatura`), **YouTube video transcripts**, and **Raster Images** (`JPEG`, `PNG`, `WEBP`, `TIFF` via **Tesseract OCR**, **Gemini Vision**, or **Google Cloud Document AI**).
  - Direct **Google Cloud Storage V4 Signed Upload/Download URLs** (`/upload-url`, `/confirm-upload`, `/download-url`) and event-driven **GCS `OBJECT_FINALIZE` $\rightarrow$ Google Pub/Sub** webhook ingestion (`/api/v1/events/gcs-finalize`) with object-generation idempotency.
  - Content-addressable SHA-256 deduplication and asynchronous background processing with Celery workers and Dead Letter Queue (DLQ) recovery.

- **Precision Hybrid Retrieval & Rust Data-Plane Acceleration**
  - Compiled **Rust `opennotebook_core` (`PyO3` + `maturin`)** extension accelerates CPU-bound data-plane hot paths while releasing the Python GIL:
    - **16.9x faster** linear-time DFA PII detection & redaction (`regex` crate + Luhn check)
    - **2.5x faster** UAX #29 Unicode sentence-boundary semantic chunking with `rayon` page parallelism
    - **34.2x faster** pre-computed Okapi BM25 inverted-index query scoring with in-memory `Arc` caching
  - Combines **dense vector similarity** in **PostgreSQL + `pgvector`** or **Qdrant** (`Vertex AI text-embedding-004` or local `BAAI/bge-small-en-v1.5`) with **sparse lexical search** (**BM25**), fused via **Reciprocal Rank Fusion (RRF)** and re-scored by a **cross-encoder reranker** (`BAAI/bge-reranker-base`).

- **Grounded Streaming Chat with Inline Citations**
  - Token-by-token responses streamed over **Server-Sent Events (SSE)**.
  - Interactive `[1]` citation chips map claims directly back to source document names, page numbers, and sections.
  - Persistent multi-session chat history, automatic notebook summaries, and **Markdown / PDF export**.

- **Pluggable Models, Vector Stores & Object Storage Backends**
  - **LLMs:** Local **Ollama** (`llama3:8b-instruct` default), **OpenAI**, **Anthropic Claude**, **Google Gemini**, plus a deterministic mock LLM stub for offline CI/testing.
  - **Embeddings:** **Vertex AI Text Embeddings** (`text-embedding-004` with `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY` task types) or local HuggingFace/BGE embeddings (`BAAI/bge-small-en-v1.5`).
  - **Vector Databases:** **PostgreSQL + `pgvector`** (`VECTOR_STORE_PROVIDER=pgvector`) or **Qdrant** (`VECTOR_STORE_PROVIDER=qdrant`).
  - **Object Storage:** Local filesystem (`local`), **Google Cloud Storage** (`gcs`), **Amazon S3** (`s3`), or **MinIO** (`minio`), tracked per source for safe multi-backend operation.

- **Enterprise Connectors, Governance & Security**
  - Built-in connector framework for **Confluence**, **SharePoint**, **Salesforce**, **Amazon S3**, **SQL databases**, **Local File Shares**, and **Generic REST APIs** with scheduled Celery Beat sync and ACL propagation.
  - Automated **PII detection and redaction** (regex & Presidio engines), prompt-injection guardrails, sensitivity classification, JWT authentication with Redis token revocation, and immutable audit logs.

- **Full-Stack Observability & RAG Evaluation**
  - Pre-wired **Prometheus** metrics, **Grafana** dashboards, **Loki + Promtail** log aggregation, **Celery Flower** task monitoring, and structured JSON logging.
  - Built-in **RAG evaluation harness** (`app.evaluation`) to benchmark retrieval recall, context precision, and answer groundedness.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    User(["User Browser"]) -->|HTTPS| Frontend["opennotebook-frontend<br/>React 19 + Vite / Nginx"]
    Frontend -->|"/api/v1/* (REST, Signed URLs & SSE)"| API["opennotebook-api<br/>FastAPI + Rust opennotebook_core (PyO3)"]
    Frontend -.->|"Direct V4 Signed PUT"| Blob[("Google Cloud Storage / S3 / Local<br/>raw/{notebook_id}/{source_id}/{file}")]

    subgraph Storage["Data, Vector & Storage Layer"]
        API -->|Async SQLAlchemy + pgvector| DB[("PostgreSQL 16 + pgvector<br/>Metadata, Auth, Audit & Chunks")]
        API -->|Dense Vector Search| Qdrant[("Qdrant / pgvector<br/>Vector Store")]
        API -->|Raw & Processed Blobs| Blob
        API -->|Broker, BM25 Cache & JWT Revocation| Redis[("Redis 7<br/>Queue & Cache")]
    end

    subgraph Async["Event-Driven & Background Ingestion"]
        Blob -->|"OBJECT_FINALIZE"| PubSub[["Google Cloud Pub/Sub<br/>+ Dead-Letter Topic"]]
        PubSub -->|"/api/v1/events/gcs-finalize"| API
        Redis --> Worker["opennotebook-worker<br/>Celery + Rust opennotebook_core"]
        Worker -->|Extract, OCR / Gemini Vision, DFA PII, UAX#29 Chunk| Blob
        Worker -->|Upsert Embeddings & Citations| Qdrant
        Worker -->|Update Source Status| DB
    end

    subgraph AI["AI & Inference Layer"]
        API -->|Grounded Prompt + SSE Stream| LLM["Gemini / Ollama / OpenAI / Anthropic"]
        Worker -->|RETRIEVAL_DOCUMENT Embeddings| Embed["Vertex AI text-embedding-004 / BGE-small"]
        API -->|Hybrid RRF + Cross-Encoder| Rerank["BGE-reranker-base"]
    end
```

### Rust Data-Plane Benchmark (`opennotebook_core` via `PyO3`)

Reproduce locally with `python -m app.scripts.benchmark_rust_vs_python`:

| Workload | Pure Python p50 | Pure Python p95 | Rust (`opennotebook_core`) p50 | Rust p95 | Speedup (p50) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **PII Scrubbing** (484 KB / 150 pages) | `62.78 ms` | `64.77 ms` | `3.72 ms` | `4.03 ms` | **16.9x** |
| **Semantic Chunking** (150 pages $\rightarrow$ chunks) | `6.54 ms` | `7.47 ms` | `2.66 ms` | `2.85 ms` | **2.5x** |
| **BM25 Query Scoring** (5,000 chunks/notebook) | `27.20 ms` | `27.86 ms` | `0.80 ms` | `0.94 ms` | **34.2x** |

### Repository Structure

```text
OpenNoteBook/
├── backend/                  # FastAPI application & RAG core (Python 3.12+)
│   ├── app/
│   │   ├── api/v1/           # Thin REST, Signed URL, Pub/Sub & SSE route handlers
│   │   ├── core/             # Config, JWT auth, rate limiting, audit logs, Prometheus metrics
│   │   ├── domain/           # Core business logic: chat, retrieval, sources, connectors, governance
│   │   ├── evaluation/       # Automated RAG evaluation dataset, LLM judge, and metrics runner
│   │   ├── infrastructure/   # DB, pgvector, Qdrant, GCS, Pub/Sub, Vertex AI, Vision, Rust bridge
│   │   ├── plugins/          # Extensible extractor & chunker plugin interfaces
│   │   └── worker/           # Celery app, DLQ handler, source processing & sync tasks
│   ├── rust/                 # Rust PyO3 native extension (`opennotebook_core`: DFA PII, UAX#29 Chunker, BM25)
│   ├── alembic/              # Alembic database migrations (including pgvector `document_chunks`)
│   └── tests/                # Unit, integration, and RAG evaluation regression suites
├── frontend/                 # React 19 + TypeScript + Tailwind CSS v4 + TanStack Query SPA
├── worker/                   # Celery worker container configuration
├── docs/                     # Architecture, local dev, GCS storage, plugins, and Cloud Run guides
├── helm/ & terraform/        # Kubernetes Helm charts and GCP Terraform infrastructure modules
├── grafana/ & prometheus/    # Pre-configured observability dashboards and scrape configs
└── docker-compose.yml        # Full local development & observability stack
```

---

## 🚀 Quick Start

### Prerequisites

- **Docker & Docker Compose v2**
- **8 GB RAM minimum** (16 GB recommended for local embeddings and Ollama inference; no GPU required)

### 1. Start the Stack

```bash
# Clone the repository
git clone https://github.com/sarkarbikram90/OpenNoteBook.git
cd OpenNoteBook

# Create your environment configuration
cp .env.example .env

# Launch all services in the background
docker compose up -d
```

### 2. Pull the Local LLM & Seed Demo Data (Optional)

If using the default local Ollama provider, pull the default instruct model and optionally seed a sample notebook:

```bash
# Pull the default local LLM into the Ollama container
docker compose exec ollama ollama pull llama3:8b-instruct

# Run database migrations and seed demo notebook + account
make db-upgrade
make seed
```

> [!TIP]
> **Default Seeded Demo Credentials:**
> - **Email:** `demo@example.com`
> - **Password:** `password123`
>
> You can also register a new account directly from the **Sign Up** tab at `http://localhost:5173/auth`.

### 3. Access Local Endpoints

| Service | URL | Notes |
|---------|-----|-------|
| **Web UI (Frontend)** | http://localhost:5173 | React 19 application |
| **API Docs (Swagger / OpenAPI)** | http://localhost:8000/docs | Interactive REST API explorer |
| **API Health Check** | http://localhost:8000/api/v1/health | Service readiness status |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | Vector collection browser |
| **Celery Flower** | http://localhost:5555 | Background task monitor |
| **Grafana** | http://localhost:3000 | Dashboards (`admin` / `change-me`) |
| **Prometheus** | http://localhost:9090 | Metrics explorer |

---

## ⚙️ Configuration

All settings are managed via environment variables in `.env` (see [.env.example](.env.example) for the complete reference).

### Model Providers

OpenNotebook defaults to local inference (`LLM_PROVIDER=ollama`, `EMBEDDING_PROVIDER=local`). To use cloud APIs, set the provider in `.env`:

```dotenv
# LLM Provider: ollama | openai | anthropic | gemini
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3:8b-instruct

# Optional Cloud LLM keys
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-3-5-sonnet-latest
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash

# Embedding & Reranker Models
EMBEDDING_PROVIDER=local          # local | openai
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-base
```

### Object Storage Providers

Choose where uploaded source documents and extracted text artifacts are stored:

```dotenv
# Storage Provider: local | gcs | s3 | minio
STORAGE_PROVIDER=local

# Google Cloud Storage (when STORAGE_PROVIDER=gcs)
GCS_BUCKET=your-private-bucket-name
GCS_PROJECT_ID=your-gcp-project-id
GCS_TIMEOUT_SECONDS=60
```

For local container development against a private Google Cloud Storage bucket using Application Default Credentials (ADC), use the included Compose override:

```bash
gcloud auth application-default login
export GOOGLE_APPLICATION_CREDENTIALS_HOST="$HOME/.config/gcloud/application_default_credentials.json"
docker compose -f docker-compose.yml -f docker-compose.gcs.yml up -d --build
```

See [docs/gcs-storage.md](docs/gcs-storage.md) for full details.

---

## 🛠️ Development & Testing

Common workflows are automated via the project [Makefile](Makefile):

```bash
make dev              # Build and start all services with hot reload
make logs             # Tail logs across all containers
make worker-logs      # Tail Celery worker output
make db-upgrade       # Apply Alembic database migrations
make seed             # Populate demo user, notebook, and sources
make lint             # Run ruff, mypy, and eslint
make format           # Format backend code with ruff
make test             # Run backend pytest suite + frontend Vitest suite
make clean            # Stop containers and remove volumes
```

### Running Tests Direct on Host

```bash
# Backend unit & evaluation regression tests
cd backend
pytest tests/evaluation tests/unit -o addopts="" -q

# Backend linting & strict type checking
ruff check app/
mypy app/

# Frontend unit tests, type checking, and lint
cd ../frontend
npm test -- --run
npm run typecheck
npm run lint
```

For step-by-step host setup outside Docker, see [docs/local-dev.md](docs/local-dev.md).

---

## ☁️ Deployment

OpenNotebook supports both serverless cloud deployment and Kubernetes orchestration:

1. **Google Cloud Run (Serverless Production):**
   - **Services:** `opennotebook-api` (FastAPI/Uvicorn) and `opennotebook-frontend` (Nginx SPA + dynamic reverse proxy).
   - **Registry:** Google Artifact Registry (`us-central1-docker.pkg.dev`).
   - **CI/CD:** Automated GitHub Actions pipeline (`.github/workflows/deploy.yml`) using keyless **Workload Identity Federation (WIF)**.
   - Full walkthrough: [docs/production-deploy.md](docs/production-deploy.md)

2. **Kubernetes & Terraform (Self-Hosted / Enterprise Cloud):**
   - Production Helm charts in [`helm/opennotebook/`](helm/opennotebook) (`make deploy`).
   - GCP infrastructure-as-code modules in [`terraform/`](terraform).

---

## 📚 Documentation

- **[Architecture Guide](docs/architecture.md)** — System topology, sequence diagrams, and design decisions
- **[Local Development Guide](docs/local-dev.md)** — Workstation setup, virtual environments, and troubleshooting
- **[Production Deployment Guide](docs/production-deploy.md)** — GCP Cloud Run, Artifact Registry, and Workload Identity Federation setup
- **[Google Cloud Storage Guide](docs/gcs-storage.md)** — Private GCS bucket provisioning, IAM roles, and ADC configuration
- **[Plugin Guide](docs/plugin-guide.md)** — Authoring custom document extractors and semantic chunkers
- **[Contributing Guide](docs/contributing.md)** — Development workflow, code standards, and pull request guidelines

---

## 🗺️ Roadmap

### Phase 1 — Core Platform & Enterprise Foundation (Completed)

- [x] Notebook & multi-session conversation management
- [x] Multi-format source ingestion (PDF, DOCX, TXT, Markdown, Web URLs, YouTube transcripts)
- [x] Raster image ingestion with Tesseract OCR (`JPEG`, `PNG`, `WEBP`, `TIFF`)
- [x] Pluggable object storage (`local`, `gcs`, `s3`, `minio`)
- [x] Token-aware semantic chunking + local BGE embeddings (`BAAI/bge-small-en-v1.5`)
- [x] Hybrid retrieval (Qdrant dense vectors + BM25 lexical search + cross-encoder reranking)
- [x] Real-time SSE streaming answers with interactive inline citations
- [x] Pluggable LLM & embedding provider abstraction (`ollama`, `openai`, `anthropic`, `gemini`)
- [x] Enterprise connectors (Confluence, SharePoint, Salesforce, S3, SQL, REST) with ACL filtering
- [x] Automated PII redaction, guardrails, audit logging, and RAG evaluation suite
- [x] Notebook export (Markdown / PDF)
- [x] Production GCP Cloud Run CI/CD with keyless Workload Identity Federation

### Phase 2 — Multimodal & Collaborative Intelligence (In Progress)

- [x] Multimodal vision extraction & diagram/chart understanding (Gemini Vision & Google Cloud Document AI OCR)
- [x] Event-driven GCS Pub/Sub `OBJECT_FINALIZE` bucket ingestion with object-generation idempotency & V4 Signed URLs
- [x] Vertex AI Text Embeddings (`text-embedding-004`) & PostgreSQL + `pgvector` vector store support
- [x] Rust `PyO3` data-plane acceleration (`opennotebook_core` for DFA PII redaction, UAX#29 chunking, and inverted-index BM25)
- [ ] Audio overviews & podcast-style two-host dialogue generation (TTS)
- [ ] Interactive knowledge graph visualization & GraphRAG traversal
- [ ] Multi-user collaborative workspaces & fine-grained RBAC UI
- [ ] Community plugin & connector marketplace

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## ⭐ Support

If you find **OpenNotebook** useful for your research or engineering workflows, please consider giving the repository a ⭐ on GitHub!
