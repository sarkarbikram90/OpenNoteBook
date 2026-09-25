# Local Development Guide

This guide walks through setting up and running **OpenNotebook** on your local workstation for development and testing.

---

## 1. Prerequisites

* **Docker & Docker Compose v2**: Installed and running (minimum 8 GB RAM allocated, 16 GB recommended).
* **Python**: 3.12 (`python --version`)
* **Node.js**: 20+ (`node --version`) and npm (`npm --version`)
* **Git**: Installed

---

## 2. Quick Start with Docker Compose

The fastest way to run all supporting services and applications locally is using Docker Compose:

```bash
# 1. Clone the repository
git clone https://github.com/sarkarbikram90/OpenNoteBook.git
cd OpenNoteBook

# 2. Configure environment
cp .env.example .env

# 3. Start all services
docker compose up -d
```

### Services & Endpoints
* **Web UI (Frontend):** [http://localhost:5173](http://localhost:5173)
* **API Documentation (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **API Health Check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
* **Qdrant Vector Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
* **MinIO Console:** [http://localhost:9001](http://localhost:9001) (`minioadmin` / `minioadmin`)

---

## 3. Running Backend Services Locally

If you prefer running the Python backend outside of Docker while keeping databases in Docker:

### 3.1 Start Backing Services
```bash
docker compose up -d postgres redis qdrant minio ollama
```

### 3.2 Setup Python Environment
```bash
# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install backend dependencies in editable mode
pip install --upgrade pip
pip install -e "./backend[dev]"
```

### 3.3 Apply Database Migrations
```bash
cd backend
alembic upgrade head
```

### 3.4 Seed Initial Data
```bash
python -m app.scripts.seed
```

### 3.5 Run the FastAPI Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3.6 Run the Celery Worker
```bash
celery -A app.worker.celery_app worker --loglevel=info --concurrency=2
```

---

## 4. Running the Frontend Locally

```bash
cd frontend

# Install Node dependencies
npm ci

# Start the Vite development server with hot-module replacement
npm run dev
# App will run at http://localhost:5173 and proxy /api requests to localhost:8000
```

---

## 5. Running Tests

### Backend Unit & Evaluation Regression Suite
```bash
cd backend

# Run the standard test suite (matching CI)
pytest tests/evaluation tests/unit -o addopts="" -q

# Run specific test file
pytest tests/unit/test_audit.py -v
```

### Frontend Tests & Type Checking
```bash
cd frontend

# Run unit tests
npm test

# Run TypeScript type check
npm run typecheck

# Lint with ESLint
npm run lint
```

---

## 6. Troubleshooting

* **PostgreSQL Connection Error:** Confirm Docker container `opennotebook-postgres` is running and healthy (`docker compose ps`).
* **Port Conflict (8000 / 5173):** Check for existing processes using `netstat -ano | findstr 8000` (Windows) or `lsof -i :8000` (macOS/Linux).
* **Missing Ollama Model:** Pull the default model using:
  ```bash
  docker compose exec ollama ollama pull llama3:8b-instruct
  ```
