import logging

import numpy as np
from fastembed import TextEmbedding

from app.config import settings

logger = logging.getLogger(__name__)

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = TextEmbedding(model_name=settings.embedding_model)
        logger.info("Embedding model loaded successfully")
    return _model


def embed_text(text: str) -> np.ndarray:
    """Embed a single text string. Returns float32 ndarray of shape (384,)."""
    model = get_model()
    vectors = list(model.embed([text]))
    return vectors[0].astype(np.float32)


def embed_batch(texts: list[str]) -> np.ndarray:
    """Embed a list of texts. Returns float32 ndarray of shape (N, 384)."""
    if not texts:
        return np.empty((0, 384), dtype=np.float32)
    model = get_model()
    vectors = list(model.embed(texts))
    return np.array(vectors, dtype=np.float32)
