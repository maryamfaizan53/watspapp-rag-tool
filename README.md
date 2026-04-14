# PSX RAG Chatbot SaaS

A multi-tenant SaaS platform that lets PSX (Pakistan Stock Exchange) investors ask questions via Telegram and WhatsApp chatbots. Answers are grounded in uploaded PDF/TXT knowledge base documents using a RAG (Retrieval-Augmented Generation) pipeline.

## Stack
- **Backend**: FastAPI 0.111, Python 3.11, SQLAlchemy (PostgreSQL/Neon), Redis, FAISS, sentence-transformers
- **LLM**: Ollama (local)
- **Transcription**: OpenAI Whisper API
- **Frontend**: React 18 + TypeScript + Vite

## Local Development

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (for Redis and Ollama)

### 2. Environment Setup
Copy `.env.example` to `.env` and fill in your credentials (especially `DATABASE_URL` for PostgreSQL/Neon).

### 3. Start Infrastructure
```bash
docker-compose up -d redis ollama
```

### 4. Backend Setup
```bash
cd backend
pip install -r requirements.txt
python scripts/seed_admin.py    # Seed first admin
uvicorn app.main:app --reload
```

### 5. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## Running with Docker
```bash
docker-compose up -d
```
(Ensure Docker Desktop is running before execution)
