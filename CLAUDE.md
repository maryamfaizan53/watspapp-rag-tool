# Claude Code Rules

This file is generated during init for the selected agent.

You are an expert AI assistant specializing in Spec-Driven Development (SDD). Your primary goal is to work with the architext to build products.

## Project: PSX RAG Chatbot SaaS

**Feature branch**: `001-psx-rag-chatbot` | **Status**: Implementation complete (all 85 tasks done)

### What this project is
A multi-tenant SaaS platform that lets PSX (Pakistan Stock Exchange) investors ask questions via Telegram and WhatsApp chatbots. Answers are grounded in uploaded PDF/TXT knowledge base documents using a RAG (Retrieval-Augmented Generation) pipeline.

### Stack
| Layer | Technology |
|---|---|
| Backend | FastAPI 0.111, Python 3.11, SQLAlchemy (PostgreSQL/Neon), Redis, FAISS, sentence-transformers |
| LLM | Ollama (local) with pybreaker circuit breaker |
| Transcription | OpenAI Whisper API |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) |
| Frontend | React 18 + TypeScript + Vite, Recharts, React Router v6 |
| Infra | Docker Compose (PostgreSQL, Redis, Ollama, backend, frontend) |

### Key directories
```
backend/
  app/api/          — FastAPI routers (auth, tenants, documents, metrics, webhooks, health)
  app/db/           — models.py (SQLAlchemy), postgres.py, redis.py, faiss_store.py
  app/schemas/      — Pydantic validation/response schemas (replacing app/models)
  app/services/     — rag.py, ingestion.py, embeddings.py, llm.py, transcription.py, usage_worker.py
  app/providers/    — telegram.py, whatsapp.py
  scripts/          — seed_admin.py
  tests/unit/       — test_rag.py, test_ingestion.py
  tests/integration/ — test_telegram_webhook.py, test_document_pipeline.py
frontend/
  src/pages/        — Login, Dashboard, Tenants, TenantDetail, Documents
  src/components/   — ChannelConfig, DocumentUploader, MetricsChart, ProtectedRoute
  src/services/api.ts
```

### Environment variables (copy .env.example → .env)
| Variable | Notes |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host/dbname` (PostgreSQL/Neon) |
| `JWT_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_EXPIRE_MINUTES` | `1440` (24h) |
| `OPENAI_API_KEY` | OpenAI — used for Whisper voice transcription only |
| `OLLAMA_BASE_URL` | `http://localhost:11434` or `http://ollama:11434` (docker) |
| `OLLAMA_MODEL` | `mistral` or `llama3` (must be pulled first) |
| `REDIS_URL` | `redis://localhost:6379` |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` |
| `FAISS_INDEX_DIR` | `./indexes` |
| `SEED_ADMIN_EMAIL` | First admin login email |
| `SEED_ADMIN_PASSWORD` | First admin login password |
| `FRONTEND_URL` | `http://localhost:5173` (dev) or production domain |
| `DISABLE_DOCS` | `false` (set `true` in prod to hide /docs) |

### Running locally
```bash
# 1. Start infrastructure
cp .env.example .env   # fill in credentials
docker-compose up -d redis ollama

# 2. Pull LLM model
docker exec psx_ollama ollama pull mistral

# 3. Run backend
cd backend && pip install -r requirements.txt
python scripts/seed_admin.py    # create first admin user
uvicorn app.main:app --reload

# 4. Run frontend
cd frontend && npm install && npm run dev

# 5. Run tests
cd backend && pytest tests/ -v
```

### Patching gotcha (important for tests)
Always patch **where a name is imported**, not where it is defined:
- ✅ `patch("app.api.documents.get_db", ...)` — patches the local reference in documents.py
- ✅ `patch("app.main.connect_db", ...)` — patches lifespan's local import
