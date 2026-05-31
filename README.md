<p align="center">
  <h1 align="center">📓 OpenNotebook</h1>
  <p align="center">
    <strong>Your private, open-source AI research assistant.</strong><br>
    Understand anything. Keep everything local.
  </p>
</p>

<p align="center">
  <a href="https://github.com/your-org/opennotebook/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/your-org/opennotebook/ci.yml?branch=main&label=CI&style=flat-square" alt="CI Status">
  </a>
  <a href="https://github.com/your-org/opennotebook/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/your-org/opennotebook?style=flat-square" alt="License">
  </a>
  <a href="https://github.com/your-org/opennotebook/stargazers">
    <img src="https://img.shields.io/github/stars/your-org/opennotebook?style=flat-square" alt="Stars">
  </a>
  <a href="https://github.com/your-org/opennotebook/issues">
    <img src="https://img.shields.io/github/issues/your-org/opennotebook?style=flat-square" alt="Issues">
  </a>
  <a href="https://github.com/your-org/opennotebook/pulls">
    <img src="https://img.shields.io/github/issues-pr/your-org/opennotebook?style=flat-square" alt="PRs">
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
- 16 GB RAM minimum (no GPU required)

### One-command start

```bash
git clone https://github.com/your-org/opennotebook
cd opennotebook
cp .env.example .env
make dev
# → http://localhost:5173
```

---

## 🏗️ Architecture

<!-- TODO: Add architecture diagram -->

See [docs/architecture.md](docs/architecture.md) for the full system design.

---

## 🗺️ Roadmap

### Phase 1 — MVP

- [ ] Notebook CRUD
- [ ] Source upload (PDF, DOCX, TXT, Markdown, URL, YouTube)
- [ ] Semantic chunking + local embeddings
- [ ] Hybrid retrieval (vector + BM25 + cross-encoder reranking)
- [ ] Streaming RAG answers with inline citations
- [ ] Conversation history
- [ ] Model registry
- [ ] Processing dashboard
- [ ] Export (Markdown / PDF)

### Phase 2 — Post-MVP

- [ ] Audio summaries (TTS)
- [ ] Podcast-style dialogue
- [ ] Multi-user workspaces + RBAC
- [ ] Knowledge graph visualisation
- [ ] Graph RAG
- [ ] OCR for scanned PDFs
- [ ] Image understanding
- [ ] Community plugin registry

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, TanStack Query, Tailwind v4 |
| Backend | FastAPI, SQLAlchemy 2 (async), Celery, Redis |
| AI / ML | Ollama, BGE-small-en-v1.5, BGE-reranker-base |
| Databases | PostgreSQL 16, Qdrant, MinIO |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki |
| Infrastructure | Docker Compose, Terraform, Helm, GitHub Actions |

---

## 🤝 Contributing

See [CONTRIBUTING.md](docs/contributing.md) for guidelines.

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

<!-- TODO: Add sponsor badge / link -->
