# Quickstart: PSX RAG Chatbot SaaS

**Branch**: `001-psx-rag-chatbot` | **Date**: 2026-04-07

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker Desktop | ≥ 24 | https://www.docker.com/products/docker-desktop |
| Docker Compose | ≥ 2.20 | Bundled with Docker Desktop |
| Python | 3.11 | https://www.python.org/downloads/ |
| Node.js | 20 LTS | https://nodejs.org/ |
| Ollama | latest | https://ollama.ai |

---

## 1. Clone and Configure Environment

```bash
git clone <repo-url>
cd watspapp-rag-tool
cp .env.example .env
```

Edit `.env` and fill in required values:

```env
# MongoDB
MONGODB_URI=mongodb://localhost:27017/psx_chatbot

# JWT
JWT_SECRET=<generate: openssl rand -hex 32>
JWT_EXPIRE_MINUTES=480

# OpenAI (Whisper transcription)
OPENAI_API_KEY=sk-...

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Redis (rate limiting + session)
REDIS_URL=redis://localhost:6379

# Embedding model
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# FAISS index storage
FAISS_INDEX_DIR=./indexes

# Admin seed user (first run only)
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=<strong-password>
```

---

## 2. Pull Required Ollama Model

```bash
ollama pull llama3
# Or: ollama pull mistral
```

Verify:
```bash
ollama list
```

---

## 3. Start Infrastructure (MongoDB + Redis)

```bash
docker compose up -d mongodb redis
```

Verify:
```bash
docker compose ps
```

---

## 4. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations / seed admin user
python -m scripts.seed_admin

# Start development server
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## 5. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Admin dashboard available at: http://localhost:5173

---

## 6. Register Telegram Webhook (development)

Use ngrok or a similar tunnel to expose local port 8000:

```bash
ngrok http 8000
```

Then register the webhook with Telegram:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://<ngrok-id>.ngrok.io/webhooks/telegram/<tenant_id>",
    "secret_token": "<generate-random-token>"
  }'
```

---

## 7. Register Twilio WhatsApp Webhook (development)

In the Twilio Console, set the WhatsApp Sandbox webhook URL to:
```
https://<ngrok-id>.ngrok.io/webhooks/whatsapp/<tenant_id>
```

---

## 8. Run Tests

```bash
# Backend
cd backend
pytest tests/ -v

# Frontend
cd frontend
npm test
```

---

## 9. Full Stack via Docker Compose

```bash
docker compose up --build
```

Services:
| Service | Port | Description |
|---------|------|-------------|
| `backend` | 8000 | FastAPI app |
| `frontend` | 5173 | React admin dashboard |
| `mongodb` | 27017 | MongoDB |
| `redis` | 6379 | Rate limiting + caching |
| `ollama` | 11434 | Local LLM |

---

## Project Structure

```text
watspapp-rag-tool/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── api/
│   │   │   ├── auth.py              # POST /auth/login, /auth/logout
│   │   │   ├── tenants.py           # CRUD /admin/tenants/*
│   │   │   ├── documents.py         # Upload/delete /admin/.../documents
│   │   │   ├── metrics.py           # GET /admin/.../metrics
│   │   │   └── webhooks.py          # POST /webhooks/telegram|whatsapp
│   │   ├── providers/
│   │   │   ├── telegram.py          # Telegram message parsing + reply
│   │   │   └── whatsapp.py          # Twilio message parsing + reply
│   │   ├── services/
│   │   │   ├── rag.py               # RAG retrieval pipeline
│   │   │   ├── ingestion.py         # Document chunking + indexing
│   │   │   ├── llm.py               # Ollama wrapper + circuit breaker
│   │   │   ├── transcription.py     # OpenAI Whisper wrapper
│   │   │   ├── embeddings.py        # MiniLM embedding service
│   │   │   └── rate_limiter.py      # slowapi + Redis
│   │   ├── models/
│   │   │   ├── tenant.py
│   │   │   ├── bot_user.py
│   │   │   ├── conversation.py
│   │   │   ├── message.py
│   │   │   ├── document.py
│   │   │   └── admin_user.py
│   │   ├── db/
│   │   │   ├── mongo.py             # Motor async client + indexes
│   │   │   └── faiss_store.py       # Per-tenant FAISS load/save
│   │   └── config.py                # Pydantic settings from .env
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
│   │   ├── services/
│   │   │   └── api.ts               # Axios client + JWT interceptor
│   │   └── main.tsx
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
└── specs/001-psx-rag-chatbot/       # This feature's documentation
```

---

## Key Development Commands

```bash
# Seed admin user
python -m scripts.seed_admin

# Re-index a tenant's documents (after model change)
python -m scripts.reindex --tenant-id <id>

# Check Ollama circuit breaker status
curl http://localhost:8000/health

# Tail backend logs
docker compose logs -f backend
```
