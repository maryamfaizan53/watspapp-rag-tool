# Research: PSX RAG Chatbot SaaS

**Branch**: `001-psx-rag-chatbot` | **Date**: 2026-04-07 | **Phase**: 0

---

## 1. PDF Chunking Strategy for Financial Documents

**Decision**: 512–1024 tokens per chunk (~2000–4000 chars) with 20% overlap (100–200 tokens).

**Rationale**: Financial PDFs require larger chunks to preserve context around regulations,
numerical statements, and clause continuity. Smaller chunks (256 tokens) cause semantic
fragmentation. 20% overlap prevents boundary misses in similarity search. Use
heading-aware recursive splitting to respect document structure.

**Alternatives considered**:
- Sliding window (variable overlap) — adds complexity without meaningful quality gain
- Fixed 256-token chunks — loses context across sentence boundaries in financial text

---

## 2. Per-Tenant FAISS Isolation

**Decision**: One FAISS index file per tenant stored at `indexes/{tenant_id}/index.faiss`.

**Rationale**: FAISS has no native namespace or multi-tenancy support. Per-file isolation
guarantees complete data privacy, independent scaling, and zero cross-tenant leakage.
Index files are small (~100 MB per 1M vectors). This is the simplest safe approach for
Phase 1 with 10–50 tenants.

**Alternatives considered**:
- Shared index with metadata filtering — operationally fragile, leakage risk
- Milvus/Pinecone — adds external service dependency, overkill for Phase 1

---

## 3. Embedding Model (English + Urdu, Self-Hosted)

**Decision**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
(384-dim, ~33 MB, covers 50+ languages including Urdu).

**Rationale**: Achieves ~95% of full-model retrieval quality at 1/12th the size.
Self-hostable and quantizable. Tested on multilingual including Urdu on MTEB benchmarks.
Suitable for financial domain with no fine-tuning required for Phase 1.

**Alternatives considered**:
- XLM-RoBERTa — better accuracy but 1.1 GB download, too heavy for Phase 1
- Ollama embeddings (mistral-embed) — couples embedding to LLM service, adds single point of failure
- Cohere multilingual API — external dependency, per-call cost

---

## 4. Telegram + WhatsApp Webhook Pattern

**Decision**: Single FastAPI router with shared async handler; platform-specific logic
extracted into `providers/telegram.py` and `providers/whatsapp.py` modules. All
message processing dispatched to background async tasks (FastAPI `BackgroundTasks`
for Phase 1; Celery if scale requires).

**Rationale**: Webhooks must reply within 3s (Telegram) / 60s (WhatsApp). Background
tasks decouple I/O-bound processing from the HTTP ack. Single router avoids microservice
overhead for Phase 1. Provider abstraction keeps code testable.

**Alternatives considered**:
- Separate microservices per channel — unnecessary complexity for Phase 1
- Celery immediately — valid upgrade path but adds Redis + worker deployment

---

## 5. Session Expiry (30-min Inactivity)

**Decision**: MongoDB TTL index (`expireAfterSeconds: 1800`) on `conversations.last_message_at`
**plus** application-level check on every message (defense in depth).

**Rationale**: TTL index handles background cleanup automatically (~60s granularity).
Application check catches race conditions and clock skew. Combined approach is both
correct and operationally simple.

**Implementation**:
```python
# On every incoming message:
if (now - conversation.last_message_at).seconds > 1800:
    start_new_conversation()
# MongoDB TTL cleans up stale Conversation documents automatically
```

**Alternatives considered**:
- Redis for sub-second expiry — adds dependency; 60s TTL granularity is acceptable here
- Application-level only — no automatic cleanup, unbounded storage growth

---

## 6. Rate Limiting (60 msg/min per Tenant)

**Decision**: `slowapi` library with Redis backend. Limit key: `tenant_id`. Default: 60/min,
configurable per subscription plan in Tenant document.

**Rationale**: `slowapi` integrates with FastAPI's dependency injection. Redis backend
scales across multiple worker instances (critical for production). Auto-cleanup of
expired buckets. Tenant-level (not IP-level) limiting matches the multi-tenant model.

**Alternatives considered**:
- Custom Redis Lua script — more control but higher implementation cost
- In-memory limiting — fails with multiple workers, not suitable for production
- Nginx rate limiting — ops dependency, can't enforce per-tenant logic

---

## 7. Ollama Failure Handling

**Decision**: Circuit breaker pattern using `pybreaker` library. Config: 3 consecutive
failures → OPEN for 30 seconds. On OPEN state: return immediate friendly error to user
(per spec clarification Q3). Health check every 5 seconds to probe recovery.

**Rationale**: Prevents cascading requests when Ollama OOMs or hangs under load.
`pybreaker` is lightweight and async-compatible. Fail-fast on responses > 10 seconds.
Aligns with spec decision: no message queuing on LLM failure.

**Alternatives considered**:
- Timeout + retry — doesn't prevent thundering herd, can worsen overload
- Fallback to OpenAI API — breaks offline/self-hosted architecture requirement
- Multiple Ollama replicas — valid Phase 2 scaling approach

---

## 8. MongoDB Multi-Tenancy Strategy

**Decision**: Single database, `tenant_id` field on every collection. Compound indexes
always include `tenant_id` as leading key.

**Rationale**: Simplifies deployment, backups, and monitoring. Scales to 100+ tenants
without per-tenant DB connection overhead. `tenant_id` in every index prevents
accidental cross-tenant queries at the query planner level.

**Alternatives considered**:
- Separate DB per tenant — strong isolation but connection pool explosion, complex ops
- Separate collection per tenant — naming conventions are fragile, no schema enforcement

---

## 9. Messages Collection: Embedded vs Separate

**Decision**: Separate `messages` collection with `conversation_id` foreign key.

**Rationale**: MongoDB 16 MB document limit. Long-running tenants accumulate conversations
indefinitely. Separate collection enables efficient pagination, independent TTL/archiving
of messages without locking Conversation documents, and simpler bulk deletes on
tenant removal.

**Alternatives considered**:
- Embedded (last N messages in Conversation) — acceptable for MVP, but blocks clean
  archiving and hits size limits under sustained use

---

## 10. Usage Counter Pattern

**Decision**: Atomic `$inc` on `Tenant.usage.message_count` per message received.
Async worker writes daily `UsageSnapshot` documents for analytics and dashboard metrics.

**Rationale**: `$inc` is a single atomic write — fast, consistent, correct for real-time
quota checks. Daily snapshots decouple analytics queries from hot-path Tenant document.

**Alternatives considered**:
- Per-event UsageEvent collection — document-per-message overhead at 500 msg/min is
  ~720K documents/day; too heavy without sharding

---

## Summary of Key Decisions

| Area | Decision |
|------|----------|
| Chunking | 512–1024 tokens, 20% overlap, heading-aware |
| Vector isolation | Per-tenant FAISS file: `indexes/{tenant_id}/index.faiss` |
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) |
| Webhook pattern | Single FastAPI router + provider abstraction + BackgroundTasks |
| Session expiry | MongoDB TTL index + app-level check |
| Rate limiting | slowapi + Redis, 60/min per tenant_id |
| LLM failure | Circuit breaker (pybreaker), immediate error response |
| DB multi-tenancy | Single DB + tenant_id everywhere |
| Messages | Separate collection |
| Usage counters | Atomic $inc + daily snapshots |
