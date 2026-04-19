import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from sqlalchemy import select

from app.api import auth, documents, health, metrics, tenants, webhooks
from app.config import settings
from app.db import faiss_store
from app.db.models import DocumentChunk, Document
from app.db.postgres import close_db, connect_db, AsyncSessionLocal
from app.db.redis import close_redis, connect_redis
from app.services import embeddings
from app.services.rate_limiter import limiter
from app.services.usage_worker import start_worker, stop_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def _rebuild_faiss_indexes() -> None:
    """Re-embed all ready chunks from DB into FAISS on startup (index is ephemeral in memory)."""
    logger.info("Rebuilding FAISS indexes from database...")
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DocumentChunk).join(Document).where(Document.status == "ready")
            )
            chunks = result.scalars().all()

        if not chunks:
            logger.info("No chunks found — FAISS index stays empty.")
            return

        # Group by tenant
        from collections import defaultdict
        import numpy as np
        by_tenant: dict = defaultdict(list)
        for chunk in chunks:
            by_tenant[str(chunk.tenant_id)].append(chunk)

        for tenant_id, tenant_chunks in by_tenant.items():
            texts = [c.text for c in tenant_chunks]
            placeholders = [f"{c.document_id}_{c.chunk_index}" for c in tenant_chunks]
            vectors = np.array([embeddings.embed_text(t) for t in texts], dtype="float32")
            faiss_store.add_vectors(tenant_id, vectors, placeholders)
            logger.info("Rebuilt FAISS index for tenant %s: %d chunks", tenant_id, len(texts))

        logger.info("FAISS rebuild complete.")
    except Exception as exc:
        logger.exception("FAISS rebuild failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Connecting to PostgreSQL...")
    await connect_db()
    logger.info("Connecting to Redis...")
    await connect_redis()
    start_worker()
    await _rebuild_faiss_indexes()
    logger.info("Application startup complete")
    yield
    # Shutdown
    stop_worker()
    logger.info("Disconnecting from PostgreSQL and Redis...")
    await close_db()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="PSX Chatbot SaaS API",
        version="0.1.0",
        description="Admin and webhook API for PSX RAG Chatbot SaaS",
        lifespan=lifespan,
        docs_url=None if settings.disable_docs else "/docs",
        redoc_url=None if settings.disable_docs else "/redoc",
    )

    # Rate limiter state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Security headers middleware
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        latency_ms = int((time.monotonic() - start) * 1000)
        tenant_id = request.path_params.get("tenant_id", "-")
        logger.info(
            "%s %s tenant=%s status=%d latency=%dms",
            request.method,
            request.url.path,
            tenant_id,
            response.status_code,
            latency_ms,
        )
        return response

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "An unexpected error occurred"},
        )

    # Routers
    app.include_router(auth.router)
    app.include_router(health.router)
    app.include_router(tenants.router)
    app.include_router(documents.router)
    app.include_router(metrics.router)
    app.include_router(webhooks.router)

    return app


app = create_app()
