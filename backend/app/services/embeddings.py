import logging

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded successfully")
    return _model


def embed_text(text: str) -> np.ndarray:
    """Embed a single text string. Returns float32 ndarray of shape (384,)."""
    model = get_model()
    vector = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vector.astype(np.float32)


def embed_batch(texts: list[str]) -> np.ndarray:
    """Embed a list of texts. Returns float32 ndarray of shape (N, 384)."""
    if not texts:
        return np.empty((0, 384), dtype=np.float32)
    model = get_model()
    vectors = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    )
    return vectors.astype(np.float32)
