# ─────────────────────────────────────────────
# OpenNotebook — Mock LLM Dockerfile
# A deterministic, Ollama-compatible stub for tests and offline dev.
# ─────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir "fastapi>=0.111,<1.0" "uvicorn[standard]>=0.29,<1.0"

COPY server.py ./

EXPOSE 11434

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:11434/').status==200 else 1)"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "11434"]
