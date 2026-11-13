<p align="center">
  <h1 align="center">📓 OpenNotebook</h1>
  <p align="center">
    <strong>Your private, open-source AI research assistant.</strong><br>
    Understand anything. Keep everything local.
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
  <a href="#-demo">Demo</a> •
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-roadmap">Roadmap</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 🎬 Demo

<!-- TODO: Record with `make seed && make dev` and add animated GIF -->
> Demo GIF coming soon.

---

## ✨ Features

<!-- TODO: Add feature comparison table vs NotebookLM -->

| Feature | OpenNotebook | NotebookLM |
|---------|:---:|:---:|
| Fully local / private | ✅ | ❌ |
| Open source | ✅ | ❌ |
| Custom model support | ✅ | ❌ |
| Streaming answers | ✅ | ✅ |
| Inline citations | ✅ | ✅ |
| Hybrid retrieval | ✅ | — |
| Plugin system | ✅ | ❌ |

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose v2
- 16 GB RAM recommended (no GPU required for local embeddings)

### One-command start

```bash
git clone https://github.com/sarkarbikram90/OpenNoteBook.git
cd OpenNoteBook
cp .env.example .env
docker compose up -d
# → Web UI: http://localhost:5173
# → API Docs: http://localhost:8000/docs
```

For detailed workstation setup, see [docs/local-dev.md](docs/local-dev.md).

---

## 🏗️ Architecture & Deployment

OpenNotebook runs locally via Docker Compose or in production on **Google Cloud Platform (GCP)**:
* **Serverless Compute:** Google Cloud Run (`opennotebook-api`, `opennotebook-frontend`)
* **Container Registry:** Google Artifact Registry (`us-central1-docker.pkg.dev`)
* **CI/CD:** GitHub Actions with keyless Workload Identity Federation (WIF)

For details, see:
* [docs/architecture.md](docs/architecture.md) — System design and data flows
* [docs/production-deploy.md](docs/production-deploy.md) — GCP Cloud Run deployment walkthrough

---

## 🗺️ Roadmap

### Phase 1 — MVP (Completed)

- [x] Notebook CRUD
- [x] Source upload (PDF, DOCX, TXT, Markdown, OCR-ready raster images, URL, YouTube transcripts)
- [x] Pluggable object storage (local, MinIO/S3, Google Cloud Storage)
- [x] Semantic chunking + local BGE embeddings
- [x] Hybrid retrieval (vector + BM25 + cross-encoder reranking)
- [x] Real-time streaming RAG answers with inline citations
- [x] Conversation history & session persistence
- [x] Pluggable model & provider abstraction
- [x] Processing dashboard
- [x] Export (Markdown / PDF)
- [x] Production Cloud Run CI/CD with WIF

### Phase 2 — Post-MVP (In Progress)

- [ ] Audio summaries (TTS)
- [ ] Podcast-style dialogue
- [ ] Multi-user workspaces + enterprise RBAC
- [ ] Knowledge graph visualisation & Graph RAG
- [ ] OCR for scanned PDFs
- [ ] Community connector registry

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, TanStack Query, Tailwind CSS v4 |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2 (async), Celery, Redis |
| AI / ML | Ollama, BGE-small-en-v1.5, BGE-reranker-base |
| Databases & Storage | PostgreSQL 16, Qdrant (Vector DB), GCS / MinIO / S3 |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki |
| Cloud Deployment | GCP Cloud Run, Artifact Registry, Workload Identity Federation |
| Local Deployment | Docker Compose |

---

## 🤝 Contributing

See [CONTRIBUTING.md](docs/contributing.md) for development workflows and PR guidelines.

---

## 🔌 Plugins

OpenNotebook supports custom extractors and chunkers.

See [Plugin Guide](docs/plugin-guide.md) for details.

---

## 📄 License

[MIT](LICENSE)

---

## ⭐ Support

If you find OpenNotebook useful, please consider giving it a star!
