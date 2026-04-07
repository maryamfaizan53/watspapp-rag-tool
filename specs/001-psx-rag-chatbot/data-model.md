# Data Model: PSX RAG Chatbot SaaS

**Branch**: `001-psx-rag-chatbot` | **Date**: 2026-04-07

---

## Overview

Single MongoDB database. All collections include `tenant_id` as a leading compound
index key. FAISS vector indexes are stored on disk per-tenant, not in MongoDB.

---

## Collections

### `tenants`

Represents a client organization using the SaaS.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `_id` | ObjectId | ✅ | Auto-generated |
| `name` | string | ✅ | Display name |
| `plan` | enum: `starter\|growth\|enterprise` | ✅ | Subscription tier |
| `status` | enum: `active\|suspended\|deleted` | ✅ | Default: `active` |
| `channels.telegram.bot_token` | string | — | Encrypted at rest |
| `channels.telegram.webhook_url` | string | — | Auto-set on token save |
| `channels.whatsapp.account_sid` | string | — | Twilio account SID |
| `channels.whatsapp.auth_token` | string | — | Encrypted at rest |
| `channels.whatsapp.from_number` | string | — | E.164 format |
| `quota.messages_per_month` | int | ✅ | Default by plan |
| `quota.rate_limit_per_minute` | int | ✅ | Default: 60 |
| `usage.message_count_month` | int | ✅ | Atomic $inc, resets monthly |
| `usage.active_users_month` | int | ✅ | Distinct BotUser count |
| `created_at` | date | ✅ | |
| `updated_at` | date | ✅ | |

**Indexes**:
- `{ status: 1 }` — list active tenants
- `{ "channels.telegram.bot_token": 1 }` — unique, sparse (webhook routing)
- `{ "channels.whatsapp.from_number": 1 }` — unique, sparse (webhook routing)

**Validator**: `status` must be in enum; `plan` must be in enum; `quota` fields must be positive integers.

---

### `admin_users`

Operators with access to the admin dashboard.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `_id` | ObjectId | ✅ | |
| `email` | string | ✅ | Unique, lowercase |
| `hashed_password` | string | ✅ | bcrypt hash |
| `role` | enum: `super_admin\|tenant_admin` | ✅ | |
| `tenant_id` | ObjectId | — | Null for super_admin |
| `is_active` | bool | ✅ | Default: true |
| `created_at` | date | ✅ | |
| `last_login_at` | date | — | |

**Indexes**:
- `{ email: 1 }` — unique

---

### `bot_users`

End-users interacting via Telegram or WhatsApp. Identity is platform-specific.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `_id` | ObjectId | ✅ | |
| `tenant_id` | ObjectId | ✅ | |
| `platform` | enum: `telegram\|whatsapp` | ✅ | |
| `platform_id` | string | ✅ | Telegram chat_id or WhatsApp E.164 number |
| `created_at` | date | ✅ | |
| `last_seen_at` | date | ✅ | Updated on every message |

**Indexes**:
- `{ tenant_id: 1, platform: 1, platform_id: 1 }` — unique compound (natural identity key)

---

### `conversations`

A session between a BotUser and the bot. Expires after 30 minutes of inactivity.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `_id` | ObjectId | ✅ | |
| `tenant_id` | ObjectId | ✅ | |
| `bot_user_id` | ObjectId | ✅ | |
| `platform` | enum: `telegram\|whatsapp` | ✅ | Denormalized for query efficiency |
| `started_at` | date | ✅ | |
| `last_message_at` | date | ✅ | Updated on every turn; drives TTL |
| `message_count` | int | ✅ | Default: 0 |
| `status` | enum: `active\|expired` | ✅ | Default: `active` |

**Indexes**:
- `{ tenant_id: 1, bot_user_id: 1, last_message_at: -1 }` — find active conversation for user
- `{ last_message_at: 1 }` — TTL index, `expireAfterSeconds: 1800` (auto-deletes after 30 min inactivity)

**State transitions**:
```
active → expired  (via TTL or explicit app-level check when gap > 30 min)
```

---

### `messages`

Individual turns within a conversation.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `_id` | ObjectId | ✅ | |
| `conversation_id` | ObjectId | ✅ | |
| `tenant_id` | ObjectId | ✅ | Denormalized for tenant-scoped queries |
| `role` | enum: `user\|bot` | ✅ | |
| `content_type` | enum: `text\|audio` | ✅ | |
| `content` | string | ✅ | Raw text or audio file reference |
| `transcription` | string | — | Populated for audio messages |
| `rag_context_ids` | [ObjectId] | — | DocumentChunk IDs used for this response |
| `timestamp` | date | ✅ | |
| `latency_ms` | int | — | End-to-end response time |

**Indexes**:
- `{ conversation_id: 1, timestamp: -1 }` — paginated message retrieval
- `{ tenant_id: 1, timestamp: -1 }` — tenant-scoped analytics

---

### `documents`

Files uploaded to a tenant's RAG knowledge base.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `_id` | ObjectId | ✅ | |
| `tenant_id` | ObjectId | ✅ | |
| `name` | string | ✅ | Original filename |
| `content_hash` | string | ✅ | SHA-256 of file content (deduplication key) |
| `file_size_bytes` | int | ✅ | Max 52,428,800 (50 MB) |
| `mime_type` | enum: `application/pdf\|text/plain` | ✅ | |
| `status` | enum: `pending\|processing\|ready\|failed` | ✅ | Default: `pending` |
| `error_message` | string | — | Populated on failure |
| `chunk_count` | int | — | Populated after ingestion |
| `uploaded_at` | date | ✅ | |
| `ready_at` | date | — | When status → ready |

**Indexes**:
- `{ tenant_id: 1, status: 1 }` — list documents by tenant and status
- `{ tenant_id: 1, content_hash: 1 }` — unique compound (deduplication)

**State transitions**:
```
pending → processing → ready
                    ↘ failed
```

---

### `document_chunks`

Metadata for FAISS-indexed text chunks. The embedding vector lives in FAISS; this
collection stores the text and provenance for retrieval display.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `_id` | ObjectId | ✅ | |
| `document_id` | ObjectId | ✅ | |
| `tenant_id` | ObjectId | ✅ | |
| `chunk_index` | int | ✅ | Position within document |
| `text` | string | ✅ | Chunk text (512–1024 tokens) |
| `faiss_vector_id` | int | ✅ | Index position in tenant's FAISS file |
| `page_number` | int | — | Source page (PDFs only) |
| `created_at` | date | ✅ | |

**Indexes**:
- `{ document_id: 1, chunk_index: 1 }` — ordered retrieval per document
- `{ tenant_id: 1 }` — bulk delete on tenant removal

---

### `usage_snapshots`

Daily aggregated usage per tenant for analytics dashboard.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `_id` | ObjectId | ✅ | |
| `tenant_id` | ObjectId | ✅ | |
| `date` | date | ✅ | UTC midnight (day boundary) |
| `message_count` | int | ✅ | |
| `active_users` | int | ✅ | Distinct BotUser count |
| `voice_message_count` | int | ✅ | |
| `avg_latency_ms` | int | ✅ | |

**Indexes**:
- `{ tenant_id: 1, date: -1 }` — unique compound (one snapshot per tenant per day)

---

## FAISS Index Layout (Filesystem)

```text
indexes/
└── {tenant_id}/
    ├── index.faiss      # FAISS flat index (384-dim MiniLM vectors)
    └── index.pkl        # Chunk ID → faiss_vector_id mapping metadata
```

One directory per tenant. Created on first document upload. Deleted on tenant deletion.

---

## Entity Relationship Summary

```
AdminUser ─── (manages) ──→ Tenant
Tenant ──────────────────→ BotUser (1:many)
Tenant ──────────────────→ Document (1:many)
BotUser ─────────────────→ Conversation (1:many)
Conversation ────────────→ Message (1:many)
Document ────────────────→ DocumentChunk (1:many)
DocumentChunk ───────────→ FAISS index (1:1 via faiss_vector_id)
Tenant ──────────────────→ UsageSnapshot (1:many, daily)
```
