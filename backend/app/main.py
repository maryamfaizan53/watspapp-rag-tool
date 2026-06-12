import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from sqlalchemy import select, update

from app.api import auth, documents, health, metrics, tenants, webhooks
from app.config import settings
from app.db import faiss_store
from app.db.models import DocumentChunk, Document
from app.db.postgres import close_db, connect_db, AsyncSessionLocal
from app.db.redis import close_redis, connect_redis
from app.services import crypto
from app.services.ingestion import rebuild_tenant_index
from app.services.rate_limiter import limiter
from app.services.usage_worker import start_worker, stop_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _enforce_production_config() -> None:
    """Refuse to boot with insecure defaults in production."""
    is_prod = settings.environment.lower() == "production"
    if settings.jwt_secret in ("", "change-me"):
        msg = "JWT_SECRET is the insecure default — set a strong random value."
        if is_prod:
            raise RuntimeError(msg)
        logger.warning(msg)
    if not crypto.encryption_enabled():
        msg = "ENCRYPTION_KEY is not set — channel secrets are stored in plaintext."
        if is_prod:
            raise RuntimeError(msg)
        logger.warning(msg)


async def _reset_stuck_documents() -> None:
    """
    Documents stuck in pending/processing were interrupted by a crash or
    restart (BackgroundTasks don't survive the process). Mark them failed so
    the admin sees a clear state and can re-upload, instead of an eternal
    'processing' spinner.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                update(Document)
                .where(Document.status.in_(["pending", "processing"]))
                .values(
                    status="failed",
                    error_message="Processing was interrupted by a server restart — please re-upload.",
                )
            )
            await db.commit()
            if result.rowcount:
                logger.warning("Reset %d stuck documents to 'failed'", result.rowcount)
    except Exception:
        logger.exception("Failed to reset stuck documents (non-fatal)")


async def _rebuild_faiss_indexes() -> None:
    """
    Rebuild every tenant's FAISS index FROM SCRATCH out of the database.

    Why from scratch: the previous implementation called add_vectors(), which
    appends to whatever index already exists on disk. On any host with a
    persistent volume (HF Spaces /data, a VPS bind mount) that DUPLICATED the
    entire index on every restart, and vectors of deleted documents lived
    forever. rebuild_index() replaces the file atomically, so disk state
    always mirrors the database.
    """
    logger.info("Rebuilding FAISS indexes from database...")
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DocumentChunk.tenant_id)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(Document.status == "ready")
                .distinct()
            )
            tenant_ids = {str(t) for t in result.scalars().all()}

        for tenant_id in tenant_ids:
            try:
                await rebuild_tenant_index(tenant_id)
            except Exception:
                logger.exception("Index rebuild failed for tenant %s (non-fatal)", tenant_id)

        # Remove disk indexes for tenants that no longer have any ready chunks
        # (deleted tenants / fully-emptied knowledge bases) so stale vectors
        # can never be searched.
        for disk_tenant in faiss_store.list_disk_tenants():
            if disk_tenant not in tenant_ids:
                faiss_store.delete_tenant_index(disk_tenant)

        logger.info("FAISS rebuild complete (%d tenants)", len(tenant_ids))
    except Exception as exc:
        logger.exception("FAISS rebuild failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    _enforce_production_config()
    logger.info("Connecting to PostgreSQL...")
    await connect_db()
    logger.info("Connecting to Redis...")
    await connect_redis()
    start_worker()
    await _reset_stuck_documents()
    await _rebuild_faiss_indexes()
    # Ensure circuit breaker starts closed on every deploy
    from app.services.llm import _breaker
    _breaker.close()
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

    # CORS — localhost dev origins only outside production
    allow_origins = [settings.frontend_url]
    if settings.environment.lower() != "production":
        allow_origins += [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys(allow_origins)),  # dedupe, keep order
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
