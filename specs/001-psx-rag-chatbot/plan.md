# Implementation Plan: PSX RAG Chatbot SaaS

**Branch**: `001-psx-rag-chatbot` | **Date**: 2026-04-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-psx-rag-chatbot/spec.md`

---

## Summary

Build a multi-tenant SaaS platform that delivers a PSX stock market Q&A chatbot via
Telegram and WhatsApp. Users ask questions in text or voice; the system transcribes
audio (Whisper), retrieves relevant PSX document chunks (FAISS + MiniLM embeddings),
and generates grounded natural-language answers (Ollama). An admin dashboard (React)
lets operators create tenants, upload knowledge-base documents, configure bot channels,
and monitor usage. Each tenant's data and vector index is fully isolated.

---

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript / Node 20 (frontend)
**Primary Dependencies**:
- FastAPI 0.111, Motor 3.x (async MongoDB), slowapi + Redis (rate limiting)
- sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` (embeddings)
- FAISS-cpu (vector store), pybreaker (circuit breaker)
- python-telegram-bot v20 (async), twilio SDK (WhatsApp)
- OpenAI SDK (Whisper transcription)
- React 18, Vite, Axios, Recharts (dashboard)

**Storage**: MongoDB Atlas (primary persistence) + FAISS files on disk (per-tenant)
**Testing**: pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend)
**Target Platform**: Linux containers (Docker), AWS ECS (production)
**Project Type**: Web application — Python backend + React frontend
**Performance Goals**: p95 text response ≤ 10s; voice response ≤ 20s; 500 msg/min sustained
**Constraints**:
- 60 msg/min rate limit per tenant (configurable)
- 50 MB max document upload
- 30-min session inactivity timeout
- 99.5% monthly uptime SLA
- Zero cross-tenant data leakage

**Scale/Scope**: 10+ concurrent tenants, ~500 msg/min peak, Phase 1 (~12 weeks)

---

## Constitution Check

*GATE: Constitution template at `.specify/memory/constitution.md` contains unfilled
placeholders — `/sp.constitution` was not completed. Using CLAUDE.md minimum acceptance
criteria as substitute gate.*

| Gate | Status | Notes |
|------|--------|-------|
| Clear, testable acceptance criteria | ✅ PASS | 8 SC + 24 FR in spec |
| Explicit error paths stated | ✅ PASS | LLM offline, rate limit, empty KB |
| Smallest viable change | ✅ PASS | Phase 1 scoped; live data feed deferred |
| No hardcoded secrets or tokens | ✅ PASS | All via `.env` (see quickstart.md) |
| No unrelated refactors | ✅ PASS | Greenfield project |

⚠️ **Action required**: Run `/sp.constitution` to fill the constitution template and
enforce project-specific gates on future features.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-psx-rag-chatbot/
├── plan.md              # This file
├── research.md          # Phase 0 research findings
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 developer quickstart
├── contracts/
│   └── openapi.yaml     # Phase 1 API contract
└── tasks.md             # Phase 2 output (/sp.tasks — not yet created)
```

### Source Code (repository root)

```text
watspapp-rag-tool/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory + lifespan
│   │   ├── config.py                # Pydantic settings (from .env)
│   │   ├── api/
│   │   │   ├── auth.py              # POST /auth/login, /auth/logout
│   │   │   ├── tenants.py           # CRUD /admin/tenants/*
│   │   │   ├── documents.py         # Upload/list/delete documents
│   │   │   ├── metrics.py           # GET usage metrics
│   │   │   └── webhooks.py          # Telegram + WhatsApp receivers
│   │   ├── providers/
│   │   │   ├── telegram.py          # Telegram message parsing + reply
│   │   │   └── whatsapp.py          # Twilio parsing + TwiML reply
│   │   ├── services/
│   │   │   ├── rag.py               # End-to-end RAG pipeline
│   │   │   ├── ingestion.py         # Chunk, embed, index documents
│   │   │   ├── llm.py               # Ollama wrapper + pybreaker
│   │   │   ├── transcription.py     # Whisper API wrapper
│   │   │   ├── embeddings.py        # MiniLM sentence-transformer
│   │   │   └── rate_limiter.py      # slowapi + Redis tenant limiter
│   │   ├── models/                  # Pydantic + Motor document models
│   │   │   ├── tenant.py
│   │   │   ├── bot_user.py
│   │   │   ├── conversation.py
│   │   │   ├── message.py
│   │   │   ├── document.py
│   │   │   └── admin_user.py
│   │   └── db/
│   │       ├── mongo.py             # Motor client + index creation
│   │       └── faiss_store.py       # Per-tenant FAISS load/save/delete
│   ├── scripts/
│   │   ├── seed_admin.py
│   │   └── reindex.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── contract/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Tenants.tsx
│   │   │   ├── TenantDetail.tsx
│   │   │   └── Documents.tsx
│   │   ├── components/
│   │   │   ├── TenantCard.tsx
│   │   │   ├── DocumentUploader.tsx
│   │   │   ├── MetricsChart.tsx
│   │   │   └── ChannelConfig.tsx
│   │   └── services/
│   │       └── api.ts               # Axios + JWT interceptor
│   ├── tests/
│   └── package.json
│
├── indexes/                          # FAISS per-tenant index files
│   └── {tenant_id}/
│       ├── index.faiss
│       └── index.pkl
│
├── docker-compose.yml
├── .env.example
└── specs/001-psx-rag-chatbot/
```

**Structure Decision**: Option 2 (Web application) — separate `backend/` and `frontend/`
directories. Python/FastAPI backend handles all bot logic, RAG pipeline, and admin API.
React frontend is the admin-only dashboard. No mobile app in scope.

---

## Architecture Overview

### Request Flow: Text Bot Query

```
User (Telegram/WhatsApp)
  → POST /webhooks/{platform}/{tenant_id}
  → Validate signature (Telegram secret_token / Twilio HMAC)
  → Check rate limit (slowapi + Redis, 60/min per tenant)
  → Dispatch to BackgroundTask
      → Resolve or create Conversation (30-min TTL check)
      → services/rag.py:
          1. Embed query (MiniLM)
          2. FAISS similarity search → top-k DocumentChunks
          3. Build prompt: [context chunks] + [conversation history] + [user query]
          4. Call Ollama (pybreaker circuit breaker, timeout 10s)
          5. If Ollama OPEN: return friendly error
      → Persist Message (user + bot turns)
      → Increment Tenant.usage.message_count ($inc)
      → Reply via Telegram API / Twilio TwiML
```

### Request Flow: Voice Message

```
User sends voice note
  → Same webhook entry point
  → Provider detects audio content type
  → services/transcription.py: download audio → Whisper API → text
  → If transcription fails: return error, do not proceed to RAG
  → Continue as text query flow above
```

### Document Ingestion Flow

```
Admin uploads file via POST /admin/tenants/{id}/documents
  → Validate file type (PDF/txt) + size (≤ 50 MB)
  → Compute SHA-256 hash → check deduplication (content_hash unique index)
  → Create Document record (status: pending)
  → Return 202 Accepted
  → BackgroundTask (services/ingestion.py):
      1. Parse PDF → raw text (pdfplumber)
      2. Chunk text (512-1024 tokens, 20% overlap, recursive splitter)
      3. Batch embed chunks (MiniLM)
      4. Load tenant FAISS index (or create new)
      5. Add vectors to FAISS + persist DocumentChunk records
      6. Save FAISS index to disk
      7. Update Document status: ready (or failed on error)
```

---

## Key Design Decisions

### D1: Per-tenant FAISS file isolation
One `indexes/{tenant_id}/index.faiss` file per tenant. Loaded into memory on first
query, cached for subsequent requests. Ensures zero cross-tenant leakage without
complex filtering logic. See `research.md §2`.

### D2: Single FastAPI process with BackgroundTasks (Phase 1)
All bot processing runs as FastAPI BackgroundTasks. Upgrade path to Celery workers
exists if 500 msg/min peak saturates the process. Deferred to Phase 2 scaling.

### D3: Messages as separate MongoDB collection
Avoids 16 MB document size limit. Independent TTL/archiving. See `research.md §9`.

### D4: Circuit breaker for Ollama (pybreaker)
3 failures → OPEN 30s. On OPEN: immediate friendly error returned (no queuing per
spec clarification). See `research.md §7`.

### D5: slowapi + Redis for rate limiting
Tenant-level (not IP-level) limiting. Redis backend scales across workers.
Default 60/min, overridable per plan in Tenant document.

---

## Complexity Tracking

No constitution violations. All design choices use the smallest viable approach for
Phase 1. Complexity is justified by functional requirements, not preference.

---

## Non-Functional Targets (from spec)

| Metric | Target | Enforcement |
|--------|--------|-------------|
| Text response p95 | ≤ 10s | `latency_ms` logged per message; alert if p95 > 8s |
| Voice response p95 | ≤ 20s | Whisper + RAG combined; logged separately |
| Document ingestion | ≤ 5 min for 50 MB | Background task; status polled by dashboard |
| Monthly uptime | 99.5% | AWS ECS health checks + CloudWatch alarm |
| Rate limit | 60 msg/min/tenant | slowapi + Redis |
| Cross-tenant leakage | Zero | Per-tenant FAISS + tenant_id compound indexes |

---

## Risks

1. **Ollama inference latency** — Local LLM may exceed 10s p95 on large prompts or
   under concurrent load. Mitigation: context window capping (top-3 chunks, 500 tokens
   max), Ollama `num_ctx` tuning, circuit breaker to fail fast.

2. **FAISS index memory under concurrent tenants** — Loading all tenant indexes
   simultaneously may exhaust RAM. Mitigation: LRU cache with configurable max loaded
   indexes (e.g., 10); evict least-recently-used on overflow.

3. **Twilio WhatsApp approval delays** — Twilio WhatsApp Business API requires account
   approval. Mitigation: Use Twilio Sandbox for development and testing; plan 2–4 weeks
   for production approval.
