---
id: 006
title: Tests Green Env Credentials Docs
stage: green
date: 2026-04-08
surface: agent
model: claude-sonnet-4-6
feature: 001-psx-rag-chatbot
branch: 001-psx-rag-chatbot
user: Maryam Faizan
command: move to the next / how to create env credentials / update claude.md
labels: ["tests", "green", "env", "documentation", "claude.md"]
links:
  spec: specs/001-psx-rag-chatbot/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/tests/unit/test_rag.py
  - backend/tests/unit/test_ingestion.py
  - backend/tests/integration/test_telegram_webhook.py
  - backend/tests/integration/test_document_pipeline.py
  - CLAUDE.md
tests:
  - backend/tests/unit/test_rag.py (12 tests)
  - backend/tests/integration/test_telegram_webhook.py (2 tests)
  - backend/tests/integration/test_document_pipeline.py (3 tests)
---

## Prompt

move to the next
---
how to create env credentials ? update claude.md file with all projects info

## Response snapshot

Ran full test suite. Fixed 4 issues:
1. Unit tests: fake IDs like "tenant1" replaced with `str(ObjectId())` — MongoDB requires valid ObjectId strings
2. Integration tests: httpx API updated (`ASGITransport(app=...)` instead of deprecated `app=` kwarg)
3. Integration tests: patched dependency at import site (`app.api.auth.verify_token` → `dependency_overrides[get_current_admin]`)
4. Integration tests: patched local bindings in consumer modules (`app.main.connect_db` not `app.db.mongo.connect_db`; `app.api.documents.process_document` not `app.services.ingestion.process_document`)

Final result: **17/17 tests pass**.

Documented env credentials in CLAUDE.md with table of all variables and how to obtain each. Updated CLAUDE.md with full project context: stack, directory map, running instructions, and the Python patching gotcha discovered during test debugging.

## Outcome

- ✅ Impact: Full test suite green. Project documentation complete for future sessions.
- 🧪 Tests: 17 passing — 12 unit, 5 integration (0 failures, 10 Pydantic v2 deprecation warnings — non-blocking)
- 📁 Files: 5 files modified — 4 test files fixed, CLAUDE.md updated with full project context
- 🔁 Next prompts: `docker-compose up --build` for full stack; configure Telegram webhook; upload PSX documents; end-to-end validation
- 🧠 Reflection: Key lesson — always patch imported names at the call site, not the definition module. Documented this as a project-level rule in CLAUDE.md so future sessions don't rediscover it.

## Evaluation notes (flywheel)

- Failure modes observed: Incorrect patch targets (import site vs definition site) — common Python mock pitfall
- Graders run and results (PASS/FAIL): pytest tests/ — 17 PASSED
- Prompt variant (if applicable): null
- Next experiment: Pydantic v2 ConfigDict migration to eliminate deprecation warnings
