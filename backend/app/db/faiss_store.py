import logging
import os
import pickle
from pathlib import Path
from threading import Lock
from typing import Optional

import faiss
import numpy as np
from cachetools import LRUCache

from app.config import settings

logger = logging.getLogger(__name__)

# LRU cache: max 10 tenant indexes in memory simultaneously
_cache: LRUCache = LRUCache(maxsize=10)
_lock = Lock()

EMBEDDING_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2 output dimension


def _tenant_dir(tenant_id: str) -> Path:
    return Path(settings.faiss_index_dir) / tenant_id


def _index_path(tenant_id: str) -> Path:
    return _tenant_dir(tenant_id) / "index.faiss"


def _meta_path(tenant_id: str) -> Path:
    return _tenant_dir(tenant_id) / "index.pkl"


def _create_empty_index() -> faiss.IndexFlatL2:
    return faiss.IndexFlatL2(EMBEDDING_DIM)


def load_index(tenant_id: str) -> tuple[faiss.IndexFlatL2, dict[int, str]]:
    """Load (index, id_map) from disk or LRU cache. Creates empty index if not found."""
    with _lock:
        if tenant_id in _cache:
            return _cache[tenant_id]

        idx_path = _index_path(tenant_id)
        meta_path = _meta_path(tenant_id)

        if idx_path.exists() and meta_path.exists():
            index = faiss.read_index(str(idx_path))
            with open(meta_path, "rb") as f:
                id_map: dict[int, str] = pickle.load(f)
            logger.info("Loaded FAISS index for tenant %s (%d vectors)", tenant_id, index.ntotal)
        else:
            index = _create_empty_index()
            id_map = {}
            logger.info("Created new empty FAISS index for tenant %s", tenant_id)

        _cache[tenant_id] = (index, id_map)
        return index, id_map


def save_index(tenant_id: str, index: faiss.IndexFlatL2, id_map: dict[int, str]) -> None:
    """Persist index and id_map to disk and update cache."""
    tenant_dir = _tenant_dir(tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(_index_path(tenant_id)))
    with open(_meta_path(tenant_id), "wb") as f:
        pickle.dump(id_map, f)

    with _lock:
        _cache[tenant_id] = (index, id_map)

    logger.info("Saved FAISS index for tenant %s (%d vectors)", tenant_id, index.ntotal)


def add_vectors(
    tenant_id: str,
    vectors: np.ndarray,
    chunk_ids: list[str],
) -> list[int]:
    """Add embedding vectors to tenant index. Returns list of faiss_vector_ids assigned."""
    index, id_map = load_index(tenant_id)
    start_id = index.ntotal
    index.add(vectors)
    new_ids = list(range(start_id, index.ntotal))
    for faiss_id, chunk_id in zip(new_ids, chunk_ids):
        id_map[faiss_id] = chunk_id
    save_index(tenant_id, index, id_map)
    return new_ids


def search(
    tenant_id: str, query_vector: np.ndarray, top_k: int = 5
) -> list[tuple[str, float]]:
    """Search for top_k nearest chunks. Returns list of (chunk_id, distance)."""
    index, id_map = load_index(tenant_id)
    if index.ntotal == 0:
        return []
    k = min(top_k, index.ntotal)
    distances, indices = index.search(query_vector.reshape(1, -1), k)
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx >= 0 and idx in id_map:
            results.append((id_map[idx], float(dist)))
    return results


def delete_tenant_index(tenant_id: str) -> None:
    """Remove tenant index from disk and cache."""
    with _lock:
        if tenant_id in _cache:
            del _cache[tenant_id]

    idx_path = _index_path(tenant_id)
    meta_path = _meta_path(tenant_id)
    tenant_dir = _tenant_dir(tenant_id)

    for path in [idx_path, meta_path]:
        if path.exists():
            path.unlink()
    if tenant_dir.exists():
        try:
            tenant_dir.rmdir()
        except OSError:
            pass  # not empty, leave dir

    logger.info("Deleted FAISS index for tenant %s", tenant_id)


def evict_from_cache(tenant_id: str) -> None:
    """Manually evict a tenant index from memory cache."""
    with _lock:
        if tenant_id in _cache:
            del _cache[tenant_id]
