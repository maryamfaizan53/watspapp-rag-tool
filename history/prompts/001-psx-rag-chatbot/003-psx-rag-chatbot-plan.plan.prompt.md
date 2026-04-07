---
id: 003
title: PSX RAG Chatbot Architecture Plan
stage: plan
date: 2026-04-07
surface: agent
model: claude-sonnet-4-6
feature: 001-psx-rag-chatbot
branch: 001-psx-rag-chatbot
user: Maryam Faizan
command: /sp.plan
labels: ["plan","rag","fastapi","mongodb","faiss","ollama","multi-tenant","whatsapp","telegram"]
links:
  spec: specs/001-psx-rag-chatbot/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-psx-rag-chatbot/plan.md
  - specs/001-psx-rag-chatbot/research.md
  - specs/001-psx-rag-chatbot/data-model.md
  - specs/001-psx-rag-chatbot/quickstart.md
  - specs/001-psx-rag-chatbot/contracts/openapi.yaml
tests:
  - "null"
---

## Prompt

/sp.plan (no additional arguments — applied to active feature 001-psx-rag-chatbot)

## Response snapshot

Phase 0 and Phase 1 planning completed. Two research agents dispatched in parallel
for RAG stack best practices and MongoDB schema design. All findings consolidated.

**Artifacts generated**:
- `research.md` — 10 key decisions with rationale and alternatives
- `data-model.md` — 8 MongoDB collections + FAISS filesystem layout
- `contracts/openapi.yaml` — Full OpenAPI 3.1 spec (auth, tenants, documents, metrics, webhooks, health)
- `quickstart.md` — Step-by-step dev setup guide + project structure
- `plan.md` — Architecture overview, request flows, design decisions, risk analysis

**Key architectural decisions**:
- Per-tenant FAISS file isolation (`indexes/{tenant_id}/index.faiss`)
- MiniLM multilingual embeddings (paraphrase-multilingual-MiniLM-L12-v2, 384-dim)
- Single FastAPI process + BackgroundTasks (Phase 1; Celery upgrade deferred)
- Circuit breaker (pybreaker) for Ollama — immediate error on OPEN state
- slowapi + Redis for 60 msg/min per-tenant rate limiting
- MongoDB TTL index (1800s) + app-level check for 30-min session expiry
- Separate messages collection (avoids 16 MB doc limit)

**Constitution note**: Template still unfilled — `/sp.constitution` should be run.

## Outcome

- ✅ Impact: Full Phase 0 + Phase 1 plan produced; ready for /sp.tasks
- 🧪 Tests: No tests yet — test strategy defined in spec (pytest + Vitest)
- 📁 Files: plan.md, research.md, data-model.md, quickstart.md, contracts/openapi.yaml
- 🔁 Next prompts: /sp.tasks
- 🧠 Reflection: Agent context updated with Python 3.11 + MongoDB. ADR suggestions
  flagged for FAISS isolation, single-DB multi-tenancy, and circuit breaker pattern.

## Evaluation notes (flywheel)

- Failure modes observed: Constitution template unfilled — gates used CLAUDE.md fallback
- Graders run and results (PASS/FAIL): Constitution gate — PASS (via CLAUDE.md criteria)
- Prompt variant (if applicable): null
- Next experiment: /sp.tasks to generate implementation task list
