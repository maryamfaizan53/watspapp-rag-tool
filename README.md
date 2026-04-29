---
title: PSX RAG Chatbot
emoji: 📈
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# PSX RAG Chatbot SaaS — Backend API

A multi-tenant SaaS platform for PSX (Pakistan Stock Exchange) investors. Users can ask questions via **Telegram** and **WhatsApp** chatbots. Answers are grounded in uploaded PDF/TXT knowledge base documents using a RAG pipeline, with live PSX market data via Gemini function calling.

## Features

- Multi-tenant RAG chatbot (FAISS + fastembed embeddings)
- Telegram & WhatsApp webhook integration
- Live PSX stock data (Yahoo Finance API + Gemini tool calling)
- Gemini 2.5 Flash Lite as LLM (free tier: 1500 req/day)
- Neon PostgreSQL + Upstash Redis (both free tier)
- Admin dashboard (React frontend — deploy separately on Vercel)

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.111, Python 3.11, SQLAlchemy async |
| Database | Neon serverless PostgreSQL |
| Cache / Rate limit | Upstash Redis (TLS) |
| LLM | Gemini 2.5 Flash Lite (function calling) |
| Embeddings | fastembed — `paraphrase-multilingual-MiniLM-L12-v2` |
| Vector search | FAISS (in-memory, persisted to `/data/indexes`) |
| Hosting | HuggingFace Spaces (Docker SDK) |

## Deployment on HuggingFace Spaces

### 1. Create a Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Choose **Docker** as the SDK
3. Set visibility to **Public** (required for free persistent storage)
4. Connect your GitHub repo **or** push this repo directly

### 2. Add Secret Variables

Go to **Settings → Variables and secrets** in your Space and add:

| Secret name | Value |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?ssl=require` |
| `JWT_SECRET` | 64-char hex string |
| `JWT_EXPIRE_MINUTES` | `1440` |
| `REDIS_URL` | `rediss://default:TOKEN@xxx.upstash.io:6379` |
| `LLM_PROVIDER` | `gemini` |
| `GEMINI_API_KEY` | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` |
| `EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `FAISS_INDEX_DIR` | `/data/indexes` |
| `ENCRYPTION_KEY` | Fernet key (see below) |
| `SEED_ADMIN_EMAIL` | `admin@yourdomain.com` |
| `SEED_ADMIN_PASSWORD` | Strong password |
| `FRONTEND_URL` | Your Vercel frontend URL |
| `OPENAI_API_KEY` | `sk-placeholder` (only needed for voice) |
| `ENVIRONMENT` | `production` |
| `DISABLE_DOCS` | `false` |

**Generate keys locally:**
```bash
# JWT secret
python3 -c "import secrets; print(secrets.token_hex(32))"

# Fernet encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Admin is seeded automatically

The app seeds the admin user on first run using `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD`. Check **Logs** in the Space to confirm startup.

### 4. Configure webhooks

Your backend URL will be:
```
https://<your-hf-username>-psx-rag-chatbot.hf.space
```

**Telegram:**
`curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<your-hf-username>-psx-rag-chatbot.hf.space/webhooks/telegram/<tenant_id>"}'``bash

```

**WhatsApp (Meta dashboard):**
- Webhook URL: `https://<your-hf-username>-psx-rag-chatbot.hf.space/webhooks/whatsapp/<tenant_id>`
- Verify token: whatever you set in your tenant's channel config

### 5. Deploy frontend on Vercel

In your Vercel project, add this environment variable:
```
VITE_API_URL = https://<your-hf-username>-psx-rag-chatbot.hf.space
```
Then redeploy.

## Local Development

```bash
cp .env.example .env   # fill in credentials
docker compose up -d redis
cd backend && pip install -r requirements.txt
python scripts/seed_admin.py
uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

## Free Tier Limits

| Service | Free limit |
|---|---|
| HuggingFace Spaces | 2 CPU, 16GB RAM — sleeps after 48h inactivity |
| Neon PostgreSQL | 0.5 GB storage, 190 compute hours/month |
| Upstash Redis | 10,000 commands/day, 256MB |
| Gemini API | 1,500 requests/day, 1M tokens/min |
| Vercel | 100GB bandwidth/month |
