# HuggingFace Spaces — PSX RAG Chatbot Backend
# HF Spaces requires port 7860 and runs as root

# --- builder stage ---
FROM python:3.11-slim AS builder

WORKDIR /build

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install --timeout=300 --retries=10 -r requirements.txt

# --- runner stage ---
FROM python:3.11-slim AS runner

WORKDIR /app

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy backend source
COPY backend/app/ app/
COPY backend/scripts/ scripts/

# Entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# HF Spaces persists /data across restarts
RUN mkdir -p /data/indexes

ENV FAISS_INDEX_DIR=/data/indexes

EXPOSE 7860

ENTRYPOINT ["/entrypoint.sh"]
