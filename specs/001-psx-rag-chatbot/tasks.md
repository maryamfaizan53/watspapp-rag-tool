# Tasks: PSX RAG Chatbot SaaS

**Input**: Design documents from `/specs/001-psx-rag-chatbot/`
**Branch**: `001-psx-rag-chatbot` | **Date**: 2026-04-07
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Tests**: Not requested in spec. Test tasks included in Polish phase only.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: User story label (US1–US5) — required for Phase 3+

---

## Phase 1: Setup

**Purpose**: Project initialization, directory structure, tooling

- [X] T001 Create backend/ directory structure per plan.md (`app/api/`, `app/providers/`, `app/services/`, `app/models/`, `app/db/`, `scripts/`, `tests/unit/`, `tests/integration/`, `tests/contract/`)
- [X] T002 Create frontend/ directory structure per plan.md (`src/pages/`, `src/components/`, `src/services/`, `tests/`)
- [X] T003 [P] Initialize Python 3.11 project in `backend/requirements.txt` (fastapi==0.111, motor, redis, slowapi, faiss-cpu, sentence-transformers, pybreaker, python-telegram-bot==20, twilio, openai, pdfplumber, pydantic-settings, python-jose[cryptography], bcrypt, uvicorn[standard], pytest, pytest-asyncio, httpx)
- [X] T004 [P] Initialize React 18 + TypeScript project with Vite in `frontend/` (`npm create vite@latest`); add dependencies: axios, recharts, react-router-dom, @types/node
- [X] T005 [P] Create `docker-compose.yml` with services: mongodb (27017), redis (6379), ollama (11434), backend (8000), frontend (5173); include volumes and healthchecks
- [X] T006 [P] Create `.env.example` with all variables per `quickstart.md`: MONGODB_URI, JWT_SECRET, JWT_EXPIRE_MINUTES, OPENAI_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL, REDIS_URL, EMBEDDING_MODEL, FAISS_INDEX_DIR, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD
- [X] T007 [P] Configure backend linting in `backend/pyproject.toml` (ruff + black; line-length 100)
- [X] T008 [P] Configure frontend linting in `frontend/.eslintrc.cjs` and `frontend/.prettierrc` (TypeScript rules, single quotes, trailing commas)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T009 Create Pydantic settings in `backend/app/config.py` (load all .env variables with types; export a `settings` singleton)
- [X] T010 Implement Motor async MongoDB client in `backend/app/db/mongo.py` (connect on startup, create all 8 collections with compound indexes and TTL index `{ last_message_at: 1 }` expireAfterSeconds=1800 on `conversations`)
- [X] T011 [P] Implement per-tenant FAISS store in `backend/app/db/faiss_store.py` (create/load/save/delete index per `tenant_id`; LRU cache max 10 loaded indexes; file layout: `indexes/{tenant_id}/index.faiss` + `index.pkl`)
- [X] T012 [P] Create Tenant model in `backend/app/models/tenant.py` (all fields from data-model.md: name, plan enum, status enum, channels, quota, usage; include `$inc` usage helper)
- [X] T013 [P] Create AdminUser model in `backend/app/models/admin_user.py` (email unique, hashed_password, role enum, tenant_id optional, is_active)
- [X] T014 [P] Create BotUser model in `backend/app/models/bot_user.py` (tenant_id, platform enum, platform_id; unique compound `tenant_id+platform+platform_id`)
- [X] T015 [P] Create Conversation model in `backend/app/models/conversation.py` (tenant_id, bot_user_id, platform, started_at, last_message_at, message_count, status; 30-min inactivity check method)
- [X] T016 [P] Create Message model in `backend/app/models/message.py` (conversation_id, tenant_id, role enum, content_type enum, content, transcription optional, rag_context_ids, timestamp, latency_ms)
- [X] T017 [P] Create Document model in `backend/app/models/document.py` (tenant_id, name, content_hash SHA-256 unique per tenant, file_size_bytes, mime_type, status enum pending→processing→ready→failed, chunk_count, uploaded_at, ready_at, error_message)
- [X] T018 [P] Create DocumentChunk model in `backend/app/models/document_chunk.py` (document_id, tenant_id, chunk_index, text, faiss_vector_id, page_number optional)
- [X] T019 Implement JWT auth utilities in `backend/app/api/auth.py` (create_access_token, verify_token dependency, hash_password/verify_password with bcrypt; POST /auth/login returns JWT; POST /auth/logout invalidates token)
- [X] T020 Implement per-tenant rate limiter in `backend/app/services/rate_limiter.py` (slowapi + Redis backend; key function extracts `tenant_id` from path; default 60/min; reads `tenant.quota.rate_limit_per_minute` from DB)
- [X] T021 Create FastAPI app factory in `backend/app/main.py` (lifespan: connect MongoDB + Redis on startup, disconnect on shutdown; register all routers; global exception handler returning `{error, message}` JSON; CORS middleware)
- [X] T022 Implement Redis async connection in `backend/app/db/redis.py` (async Redis client via `redis.asyncio`; expose `get_redis` dependency)
- [X] T023 Create admin seed script in `backend/scripts/seed_admin.py` (create first AdminUser from SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD env vars; idempotent — skip if email exists)
- [X] T024 Create `indexes/` directory with `.gitkeep`; update `.gitignore` to exclude `indexes/**/*.faiss` and `indexes/**/*.pkl` but keep `.gitkeep`
- [X] T025 Create `UsageSnapshot` model in `backend/app/models/usage_snapshot.py` (tenant_id, date, message_count, active_users, voice_message_count, avg_latency_ms; unique compound `tenant_id+date`)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Telegram Text Q&A (Priority: P1) 🎯 MVP

**Goal**: Investors can ask PSX stock questions via Telegram and receive grounded answers from the knowledge base within 10 seconds.

**Independent Test**: Send "What is the P/E ratio of OGDC?" to Telegram bot; verify grounded answer returned within 10s. Send non-PSX question; verify polite refusal. Send with empty KB; verify "no data available" fallback.

- [X] T026 [P] [US1] Implement MiniLM embedding service in `backend/app/services/embeddings.py` (load `paraphrase-multilingual-MiniLM-L12-v2` on startup; `embed_text(text) → np.ndarray`; `embed_batch(texts) → np.ndarray`; 384-dim output)
- [X] T027 [P] [US1] Implement Ollama LLM wrapper in `backend/app/services/llm.py` (async HTTP POST to OLLAMA_BASE_URL/api/generate; pybreaker circuit breaker: 3 failures → OPEN 30s; 10s timeout; on OPEN state raise `LLMUnavailableError`)
- [X] T028 [US1] Implement RAG pipeline in `backend/app/services/rag.py` (`answer_query(tenant_id, query_text, conversation_history) → str`: embed query → FAISS top-5 search → build context string from DocumentChunk texts → build prompt with context + last 5 conversation turns + user query → call LLM → return answer string)
- [X] T029 [US1] Implement empty-KB and out-of-scope fallbacks in `backend/app/services/rag.py` (if FAISS returns 0 results: return configured fallback message; include system prompt instruction to refuse non-PSX questions)
- [X] T030 [US1] Implement session management in `backend/app/services/rag.py` (`get_or_create_conversation(tenant_id, bot_user_id, platform)`: find latest Conversation where `last_message_at > now - 30min`; if none or expired: create new Conversation; update `last_message_at` on each turn)
- [X] T031 [US1] Implement BotUser lookup/create in `backend/app/services/bot_user_service.py` (`get_or_create_bot_user(tenant_id, platform, platform_id) → BotUser`; upsert with `last_seen_at` update)
- [X] T032 [US1] Implement Telegram provider in `backend/app/providers/telegram.py` (parse Telegram `Update` object: extract `chat_id`, `message.text`; detect content type text vs voice; `send_text_reply(bot_token, chat_id, text)` using Telegram Bot API)
- [X] T033 [US1] Register POST `/webhooks/telegram/{tenant_id}` in `backend/app/api/webhooks.py` (validate `secret_token` query param matches stored token; look up Tenant by `tenant_id`; enforce rate limit; dispatch `BackgroundTask(handle_telegram_message, update, tenant)`)
- [X] T034 [US1] Implement `handle_telegram_message` BackgroundTask in `backend/app/api/webhooks.py` (get/create BotUser → get/create Conversation → call `rag.answer_query` → send reply via Telegram → persist user Message + bot Message → `$inc` tenant usage counter)
- [X] T035 [US1] Handle `LLMUnavailableError` in `handle_telegram_message` in `backend/app/api/webhooks.py` (send user-friendly error: "Service temporarily unavailable, please try again shortly"; log error)
- [X] T036 [US1] Register GET `/health` in `backend/app/api/health.py` (probe MongoDB ping, Ollama `/api/tags`, Redis ping; return `{status, version, dependencies: {mongodb, ollama, redis}}` as ok/degraded/down)

**Checkpoint**: User Story 1 fully functional and independently testable — send Telegram messages, get RAG answers

---

## Phase 4: User Story 2 — Voice Messages (Priority: P2)

**Goal**: Investors can send voice notes to the bot and receive transcribed + grounded answers within 20 seconds.

**Independent Test**: Send a voice note asking about a PSX stock to Telegram bot; verify transcription generated and relevant text answer returned within 20s. Send >5min voice note; verify duration error returned.

- [X] T037 [P] [US2] Implement Whisper transcription service in `backend/app/services/transcription.py` (`transcribe_audio(file_bytes, mime_type) → str`: download audio bytes → call `openai.audio.transcriptions.create(model="whisper-1")` → return text; raise `TranscriptionError` on failure or empty result)
- [X] T038 [US2] Extend Telegram provider in `backend/app/providers/telegram.py` to detect voice/audio messages: extract `message.voice` or `message.audio`; check `duration` field — if > 300s raise `AudioTooLongError`; download file bytes from Telegram File API; return audio bytes + mime_type
- [X] T039 [US2] Extend `handle_telegram_message` BackgroundTask in `backend/app/api/webhooks.py` to branch on content type: if audio → call `transcription.transcribe_audio` → set `transcription` field on Message → use transcribed text as RAG query; handle `TranscriptionError` (reply: "Could not understand audio, please resend"); handle `AudioTooLongError` (reply: "Voice note exceeds 5-minute limit")
- [X] T040 [US2] Store transcription text in `Message.transcription` field in `backend/app/models/message.py` when saving audio user messages

**Checkpoint**: Voice messages independently testable alongside Telegram text Q&A

---

## Phase 5: User Story 3 — Admin Document Upload (Priority: P3)

**Goal**: Admins can upload PDF/text documents to a tenant's knowledge base via the dashboard; content becomes queryable by the bot within 5 minutes.

**Independent Test**: Log in to admin dashboard → select a tenant → upload a PSX annual report PDF → wait for status "ready" → send Telegram question whose answer only exists in that document → verify bot answers correctly.

- [X] T041 [P] [US3] Implement document text extraction + chunking in `backend/app/services/ingestion.py` (`chunk_document(file_bytes, mime_type) → List[str]`: parse PDF with pdfplumber or read plain text; split using recursive character splitter, chunk_size=1024 tokens (~4000 chars), overlap=20%)
- [X] T042 [US3] Implement FAISS index update in `backend/app/services/ingestion.py` (`ingest_chunks(tenant_id, document_id, chunks) → int`: batch embed chunks → load tenant FAISS index → add vectors → save index to disk → create DocumentChunk records in MongoDB → return chunk_count)
- [X] T043 [US3] Implement full ingestion BackgroundTask in `backend/app/services/ingestion.py` (`process_document(tenant_id, document_id)`: update status pending→processing → call chunk + ingest → update status→ready + chunk_count + ready_at; on any exception: update status→failed + error_message)
- [X] T044 [US3] Implement SHA-256 deduplication check in `backend/app/api/documents.py` (compute `hashlib.sha256(file_bytes).hexdigest()`; query `{ tenant_id, content_hash }`; return HTTP 409 if exists)
- [X] T045 [P] [US3] Register POST `/admin/tenants/{tenant_id}/documents` in `backend/app/api/documents.py` (require BearerAuth; validate `mime_type` in `application/pdf, text/plain`; validate `file_size_bytes ≤ 52428800`; dedup check; create Document record status=pending; dispatch `BackgroundTask(process_document)`; return HTTP 202)
- [X] T046 [P] [US3] Register GET `/admin/tenants/{tenant_id}/documents` in `backend/app/api/documents.py` (require BearerAuth; list documents with optional `?status=` filter; return paginated list)
- [X] T047 [P] [US3] Register GET `/admin/tenants/{tenant_id}/documents/{document_id}` in `backend/app/api/documents.py` (require BearerAuth; single document detail with status)
- [X] T048 [P] [US3] Register DELETE `/admin/tenants/{tenant_id}/documents/{document_id}` in `backend/app/api/documents.py` (require BearerAuth; delete DocumentChunk records → remove vectors from FAISS index → delete Document record → save FAISS index)
- [X] T049 [P] [US3] Create Axios API client in `frontend/src/services/api.ts` (base URL from env; JWT Bearer interceptor; `uploadDocument(tenantId, file)`, `listDocuments(tenantId)`, `deleteDocument(tenantId, docId)`)
- [X] T050 [P] [US3] Create DocumentUploader component in `frontend/src/components/DocumentUploader.tsx` (file picker accepting PDF and .txt; file size validation client-side ≤50MB; upload progress indicator; error display for 409/413/415 responses)
- [X] T051 [US3] Create Documents page in `frontend/src/pages/Documents.tsx` (list documents with name, status badge, uploaded_at, chunk_count; delete button with confirmation; embed DocumentUploader; poll status every 10s for processing documents)

**Checkpoint**: Admin can upload documents; bot queries reflect new content

---

## Phase 6: User Story 4 — Admin Tenant Management (Priority: P4)

**Goal**: SaaS operator can create/manage client tenants, configure bot channels, set quotas, and view usage metrics via the admin dashboard, with full data isolation between tenants.

**Independent Test**: Create two tenants (A and B) with separate knowledge bases and channel configs via dashboard; send query from Tenant A bot; verify no Tenant B data returned.

- [X] T052 [P] [US4] Register GET `/admin/tenants` in `backend/app/api/tenants.py` (require BearerAuth; paginated list with optional `?status=` filter)
- [X] T053 [P] [US4] Register POST `/admin/tenants` in `backend/app/api/tenants.py` (require BearerAuth; create Tenant with default quota by plan; return HTTP 409 on duplicate name)
- [X] T054 [P] [US4] Register GET `/admin/tenants/{tenant_id}` in `backend/app/api/tenants.py` (require BearerAuth)
- [X] T055 [P] [US4] Register PUT `/admin/tenants/{tenant_id}` in `backend/app/api/tenants.py` (require BearerAuth; update name, plan, quota fields)
- [X] T056 [US4] Register DELETE `/admin/tenants/{tenant_id}` in `backend/app/api/tenants.py` (require BearerAuth; cascade delete: DocumentChunk → Document → Message → Conversation → BotUser → FAISS index directory → Tenant)
- [X] T057 [US4] Register PUT `/admin/tenants/{tenant_id}/channels` in `backend/app/api/tenants.py` (require BearerAuth; store Telegram bot_token + WhatsApp Twilio credentials; encrypt sensitive fields at rest using Fernet symmetric encryption with key from env)
- [X] T058 [P] [US4] Register GET `/admin/tenants/{tenant_id}/metrics` in `backend/app/api/metrics.py` (require BearerAuth; aggregate from UsageSnapshot by `?from=&to=` date range; return daily breakdown)
- [X] T059 [US4] Implement daily UsageSnapshot worker in `backend/app/services/usage_worker.py` (triggered by FastAPI startup scheduler or cron: for each active tenant compute daily stats from messages → upsert UsageSnapshot; use `asyncio` background loop or `APScheduler`)
- [X] T060 [P] [US4] Extend Axios API client in `frontend/src/services/api.ts` (add: `login`, `logout`, `listTenants`, `createTenant`, `updateTenant`, `deleteTenant`, `configureChannels`, `getTenantMetrics`)
- [X] T061 [P] [US4] Create Login page in `frontend/src/pages/Login.tsx` (email/password form; POST /auth/login; store JWT in localStorage; redirect to `/dashboard` on success; show error on 401)
- [X] T062 [P] [US4] Create ProtectedRoute component in `frontend/src/components/ProtectedRoute.tsx` (check JWT in localStorage; redirect to /login if absent or expired)
- [X] T063 [P] [US4] Create Dashboard page in `frontend/src/pages/Dashboard.tsx` (total tenants count, total messages today, active tenants; link to Tenants list)
- [X] T064 [P] [US4] Create Tenants list page in `frontend/src/pages/Tenants.tsx` (table: name, plan, status, message count this month, created_at; Create button; Delete with confirmation)
- [X] T065 [P] [US4] Create TenantDetail page in `frontend/src/pages/TenantDetail.tsx` (tabs: Overview, Channels, Documents, Metrics; edit name/plan/quota inline)
- [X] T066 [P] [US4] Create ChannelConfig component in `frontend/src/components/ChannelConfig.tsx` (Telegram: bot_token input + save/clear; WhatsApp: account_sid + auth_token + from_number; show "configured" indicator without exposing secrets)
- [X] T067 [P] [US4] Create MetricsChart component in `frontend/src/components/MetricsChart.tsx` (Recharts LineChart: daily message_count + active_users over selected date range; date range picker)
- [X] T068 [US4] Add React Router v6 routes in `frontend/src/main.tsx`: `/login` → Login, `/dashboard` → Dashboard (protected), `/tenants` → Tenants (protected), `/tenants/:id` → TenantDetail (protected), `/tenants/:id/documents` → Documents (protected)

**Checkpoint**: Full admin onboarding flow — create tenant, configure channels, upload docs, view metrics — independently testable

---

## Phase 7: User Story 5 — WhatsApp Bot (Priority: P5)

**Goal**: Investors can ask PSX questions via WhatsApp and receive the same RAG-grounded answers as on Telegram within 15 seconds.

**Independent Test**: Configure Twilio WhatsApp sandbox for a test tenant; send "What is OGDC's EPS?" via WhatsApp; verify correct bot response within 15s. Send voice note; verify transcribed and answered.

- [X] T069 [P] [US5] Implement Twilio WhatsApp provider in `backend/app/providers/whatsapp.py` (parse `application/x-www-form-urlencoded` webhook body: extract `From`, `Body`, `MediaUrl0`, `MediaContentType0`; validate `X-Twilio-Signature` HMAC using twilio SDK's `RequestValidator`; `send_text_reply(account_sid, auth_token, from_number, to_number, text)` using twilio `Client.messages.create`)
- [X] T070 [US5] Register POST `/webhooks/whatsapp/{tenant_id}` in `backend/app/api/webhooks.py` (validate Twilio HMAC signature; look up Tenant by `tenant_id`; enforce rate limit; dispatch `BackgroundTask(handle_whatsapp_message, form_data, tenant)`; return HTTP 200 with empty TwiML `<Response/>`)
- [X] T071 [US5] Implement `handle_whatsapp_message` BackgroundTask in `backend/app/api/webhooks.py` (mirror Telegram handler: get/create BotUser platform=whatsapp → session → RAG → reply via Twilio; detect audio via MediaContentType → transcribe → RAG; persist messages; increment usage counter)
- [X] T072 [US5] Handle WhatsApp-specific errors in `backend/app/providers/whatsapp.py` (Twilio signature validation failure → return HTTP 403; Twilio API send failure → log error, do not re-raise to avoid webhook retry loop)

**Checkpoint**: WhatsApp text + voice Q&A fully functional alongside Telegram

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Observability, security hardening, production config, tests

- [X] T073 [P] Add structured request logging middleware in `backend/app/main.py` (log: timestamp, method, path, tenant_id from path params, status_code, latency_ms; JSON format for log aggregation)
- [X] T074 [P] Add CORS middleware in `backend/app/main.py` (allow `FRONTEND_URL` from env; allow Authorization header; methods: GET, POST, PUT, DELETE)
- [X] T075 [P] Add security headers middleware in `backend/app/main.py` (X-Content-Type-Options: nosniff; X-Frame-Options: DENY; Referrer-Policy: no-referrer)
- [X] T076 [P] Create multi-stage production Dockerfile in `backend/Dockerfile` (builder stage: pip install; runner stage: python:3.11-slim, non-root user, copy app only)
- [X] T077 [P] Create frontend production Dockerfile in `frontend/Dockerfile` (builder: `npm run build`; runner: nginx:alpine serving `dist/`)
- [X] T078 [P] Update `docker-compose.yml` with production config (named volumes for MongoDB data + FAISS indexes; restart: unless-stopped; healthcheck for each service)
- [X] T079 Implement FAISS LRU cache eviction in `backend/app/db/faiss_store.py` (use `functools.lru_cache` or `cachetools.LRUCache`; max 10 concurrent tenant indexes in memory; log eviction events)
- [X] T080 [P] Write unit tests for RAG pipeline in `backend/tests/unit/test_rag.py` (mock FAISS search, mock LLM; test empty KB fallback, out-of-scope refusal, session expiry logic)
- [X] T081 [P] Write unit tests for ingestion service in `backend/tests/unit/test_ingestion.py` (mock embeddings + FAISS; test chunking output, dedup check, status transitions)
- [X] T082 [P] Write integration test: Telegram webhook → RAG → reply in `backend/tests/integration/test_telegram_webhook.py` (use httpx TestClient; mock Telegram API send; verify message persisted + reply sent)
- [X] T083 [P] Write integration test: document upload → ingestion → query in `backend/tests/integration/test_document_pipeline.py` (upload PDF fixture → wait for status ready → query RAG → verify answer references uploaded content)
- [X] T084 [P] Add OpenAPI docs config in `backend/app/main.py` (title, version, description; disable docs in production via env flag `DISABLE_DOCS=true`)
- [X] T085 Run quickstart.md validation: complete full end-to-end setup from clean clone; update quickstart.md with any discovered gaps or corrected commands

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **Phase 3 (US1)**: Depends on Phase 2 only — no dependency on US2–US5
- **Phase 4 (US2)**: Depends on Phase 2 + extends Phase 3 providers — start after T032
- **Phase 5 (US3)**: Depends on Phase 2 + T026 (embeddings) — start after T026
- **Phase 6 (US4)**: Depends on Phase 2 only — fully independent of US1–US3
- **Phase 7 (US5)**: Depends on Phase 2 + mirrors Phase 3 handler — start after T034
- **Phase 8 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependency on other user stories
- **US2 (P2)**: Can start after T032 (Telegram provider exists) — extends US1's webhook handler
- **US3 (P3)**: Can start after Phase 2 + T026 (embedding service exists)
- **US4 (P4)**: Can start after Phase 2 — fully independent of US1/US2/US3
- **US5 (P5)**: Can start after T034 (handler pattern established in US1)

### Within Each User Story

- Models before services
- Services before endpoints
- Backend endpoints before frontend pages
- Core implementation before error handling additions

### Parallel Opportunities

- All Phase 1 tasks T001–T008 can run in parallel
- All Phase 2 model tasks T012–T018 can run in parallel (different files)
- US3 backend (T041–T048) can run in parallel with US4 backend (T052–T059) after Phase 2
- All frontend page tasks within a story can run in parallel (different files)

---

## Parallel Execution Examples

### Phase 2 Foundational — Models in parallel

```
Parallel batch A (models — all different files):
  T012: tenant.py
  T013: admin_user.py
  T014: bot_user.py
  T015: conversation.py
  T016: message.py
  T017: document.py
  T018: document_chunk.py
  T025: usage_snapshot.py

Then sequential:
  T010: mongo.py (creates indexes referencing all models)
  T019: auth.py (depends on admin_user model)
```

### Phase 3 US1 — Core services

```
Parallel batch (different services, no deps):
  T026: embeddings.py
  T027: llm.py
  T032: telegram.py provider

Then sequential:
  T028: rag.py (depends on embeddings + llm)
  T029: rag.py fallbacks (extends T028)
  T030: rag.py sessions (extends T028)
  T033: webhooks.py route (depends on T032 + T028)
  T034: webhooks.py BackgroundTask (depends on T033)
```

### Phase 6 US4 — Frontend pages in parallel

```
Parallel batch (all different files):
  T061: Login.tsx
  T062: ProtectedRoute.tsx
  T063: Dashboard.tsx
  T064: Tenants.tsx
  T065: TenantDetail.tsx
  T066: ChannelConfig.tsx
  T067: MetricsChart.tsx

Then sequential:
  T068: main.tsx routing (depends on all pages existing)
```

---

## Implementation Strategy

### MVP (User Story 1 Only — Telegram Text Q&A)

1. Complete Phase 1: Setup (T001–T008)
2. Complete Phase 2: Foundational (T009–T025) ← **CRITICAL**
3. Complete Phase 3: User Story 1 (T026–T036)
4. **STOP and VALIDATE**: Send Telegram questions, verify RAG answers, check 10s latency
5. Demo to stakeholders — MVP is functional

### Incremental Delivery

1. **Week 1–2**: Phase 1 + Phase 2 → Foundation ready
2. **Week 3**: Phase 3 (US1) → Telegram bot answers questions → **Demo**
3. **Week 4**: Phase 4 (US2) → Voice message support added
4. **Week 5–6**: Phase 5 (US3) → Admin can upload documents via dashboard
5. **Week 7–8**: Phase 6 (US4) → Full admin dashboard with tenant management
6. **Week 9**: Phase 7 (US5) → WhatsApp channel live
7. **Week 10**: Phase 8 → Polish, tests, production config

### Parallel Team Strategy (2 developers)

After Phase 2 completes:
- **Dev A**: US1 (T026–T036) → US2 (T037–T040) → US5 (T069–T072)
- **Dev B**: US3 backend (T041–T048) → US4 backend (T052–T059) → US3/US4 frontend

---

## Task Count Summary

| Phase | Tasks | Parallelizable |
|-------|-------|---------------|
| Phase 1: Setup | 8 (T001–T008) | 7 |
| Phase 2: Foundational | 17 (T009–T025) | 11 |
| Phase 3: US1 Telegram Q&A | 11 (T026–T036) | 4 |
| Phase 4: US2 Voice | 4 (T037–T040) | 1 |
| Phase 5: US3 Doc Upload | 11 (T041–T051) | 8 |
| Phase 6: US4 Admin CRUD | 17 (T052–T068) | 14 |
| Phase 7: US5 WhatsApp | 4 (T069–T072) | 1 |
| Phase 8: Polish | 13 (T073–T085) | 10 |
| **Total** | **85** | **56** |

---

## Notes

- `[P]` tasks = different files, no blocking dependencies within same phase
- `[USn]` label maps every task to its user story for traceability
- Each user story phase ends with an explicit **Checkpoint** for independent validation
- Tests are in Phase 8 (not requested in spec); add TDD task tags if TDD approach is chosen
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently before proceeding
