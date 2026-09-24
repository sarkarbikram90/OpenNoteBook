# Enterprise RAG — Stage Plan (extend OpenNotebook)

Ratified by ADR 0001. Work proceeds one stage at a time. A stage is done only when
its exit criteria pass; do not start the next stage before confirmation.

Legend: **DONE** — exists and works. **PARTIAL** — exists but needs work to meet the
target. **MISSING** — net-new work.

| Stage | Target | Repo status | Work required | Exit criteria |
|---|---|---|---|---|
| 0 | Scaffolding & decisions | DONE (this stage) | Ratify stack; fix boot blocker; pre-commit; mock LLM; decision records | `docker compose up` clean; `/api/v1/health` returns 200; pre-commit installed; ADR + plan committed |
| 1 | Data lake & storage abstraction | DONE | Verify only | Sample PDF/DOCX/JSON lands in MinIO with checksum + metadata |
| 2 | Ingestion framework + first connector | PARTIAL | Use checksums for dedup; Presidio; local file-share connector | Mixed folder ingest: dedup, redaction, metadata verified |
| 3 | Chunking, embeddings, vector store | DONE | Add Qdrant payload indexes; true tokenizer | Direct vector query returns relevant chunks; re-run is idempotent |
| 4 | Enterprise connectors | MISSING | SharePoint, Confluence, SQL, Salesforce, REST; OAuth; delta sync | Each connector verified against live/mocked source |
| 5 | Permission-aware retrieval | PARTIAL | Wire security context into serving; IdP group to ACL map | Two users, different groups, same query, different results; negative tests pass |
| 6 | RAG orchestration service | PARTIAL | Add `/feedback`; provider abstraction; wire ACL step | End-to-end cited answer; provider switchable via env |
| 7 | Chat frontend | PARTIAL | OIDC login; feedback buttons | Login as test user, ask question, see cited answer, submit feedback |
| 8 | Governance, observability, security | PARTIAL | Query audit (user, chunk IDs, ts); prompt-injection guardrails; secrets (Vault/KMS) | Replay a query from audit logs; all stages traced |
| 9 | Incremental re-indexing & freshness | PARTIAL | Change detection (cron/webhook); scheduler; side-by-side model re-index | Edit a source doc; index updates within SLA |
| 10 | Evaluation & quality | MISSING | Gold Q&A set; recall@K; groundedness; hallucination rate; regression gate | Eval report with baseline metrics; runs on every deploy |
| 11 | Production deployment | PARTIAL | HPA template; blue/green or canary; on-prem K8s hardening | Deploy to staging; eval passes; promote to prod |

## Stage 0 exit checklist (this stage)

- [x] Boot-blocking import fixed (`backend/app/api/v1/connectors.py`)
- [x] Stack ratified — `docs/decisions/0001-adopt-and-stack.md`
- [ ] `docker compose up -d` starts all core services healthy
- [ ] `GET /api/v1/health` returns `{"status":"ok"}`
- [ ] `.pre-commit-config.yaml` present and `pre-commit run --all-files` passes
- [ ] Mock LLM service available for deterministic/offline tests
- [ ] `scripts/check_imports.py` reports zero broken first-party imports

## Known risks carried forward

- **High:** permission-aware retrieval not wired (Stage 5). Blocks multi-user use.
- **High:** connector sync not idempotent (Stage 2/4).
- **Medium:** no evaluation harness (Stage 10).
- **Medium:** default secrets in Helm/config must be replaced before any shared deployment (Stage 8).
