# --- builder stage ---
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install --timeout=300 --retries=10 -r requirements.txt

# --- runner stage ---
FROM python:3.11-slim AS runner

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

COPY --from=builder /install /usr/local

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY app/ app/
COPY scripts/ scripts/

# FAISS index directory and fastembed cache — must be owned by appuser
RUN mkdir -p indexes /tmp/fastembed_cache /tmp/hf_cache \
    && chown -R appuser:appgroup indexes /tmp/fastembed_cache /tmp/hf_cache

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
