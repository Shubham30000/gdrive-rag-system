"""
search/faiss_store.py
Manages a FAISS IndexFlatIP index (cosine similarity after L2 normalisation).

Responsibilities
----------------
• add_chunks()   – encode + index a list of chunk dicts
• search()       – embed a query, return top-k chunks above min_score
• save() / load()– persist index + metadata to disk
• clear()        – wipe everything (for a full re-sync)
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np

from config import settings
from embedding.embedder import encode, get_embedding_dim

logger = logging.getLogger(__name__)


class FAISSStore:
    def __init__(self):
        self._dim: Optional[int] = None
        self._index: Optional[faiss.IndexFlatIP] = None
        # int → chunk dict
        self._metadata: Dict[int, Dict[str, Any]] = {}
        self._next_id: int = 0

    # ─── private ────────────────────────────────────────────────────────────

    def _ensure_index(self):
        if self._index is None:
            self._dim = get_embedding_dim()
            self._index = faiss.IndexFlatIP(self._dim)
            logger.info("Created new FAISS index (dim=%d)", self._dim)

    # ─── public interface ────────────────────────────────────────────────────

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Embed and index a list of chunk dicts.

        Returns the number of chunks actually added.
        """
        if not chunks:
            return 0

        self._ensure_index()
        texts = [c["text"] for c in chunks]

        logger.info("Embedding %d chunks …", len(texts))
        vectors = encode(texts, batch_size=32, show_progress=True)

        self._index.add(vectors)

        for i, chunk in enumerate(chunks):
            self._metadata[self._next_id + i] = chunk

        self._next_id += len(chunks)
        logger.info("Index now contains %d vectors", self._index.ntotal)
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        doc_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Embed the query and retrieve the most relevant chunks.

        Args:
            query:     Natural-language question.
            top_k:     Number of results (default: settings.top_k).
            min_score: Minimum cosine similarity (default: settings.min_score).
            doc_id:    Optional: restrict results to a specific document.

        Returns:
            List of result dicts, each with an extra 'score' key.
        """
        if self._index is None or self._index.ntotal == 0:
            logger.warning("FAISS index is empty – no results")
            return []

        top_k = top_k or settings.top_k
        min_score = min_score if min_score is not None else settings.min_score

        q_vec = encode(query)                   # shape (1, dim)
        distances, indices = self._index.search(q_vec, top_k * 3)  # over-fetch for filtering

        results: List[Dict[str, Any]] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            score = float(dist)
            if score < min_score:
                continue
            chunk = dict(self._metadata.get(idx, {}))
            if not chunk:
                continue
            if doc_id and chunk.get("doc_id") != doc_id:
                continue
            chunk["score"] = round(score, 4)
            results.append(chunk)
            if len(results) >= top_k:
                break

        return results

    # ─── persistence ─────────────────────────────────────────────────────────

    def save(self):
        if self._index is None:
            logger.warning("Nothing to save – index is empty")
            return

        Path(settings.faiss_index_path).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, settings.faiss_index_path)

        with open(settings.metadata_path, "w", encoding="utf-8") as f:
            # JSON keys must be strings
            json.dump(
                {str(k): v for k, v in self._metadata.items()}, f, ensure_ascii=False, indent=2
            )

        logger.info(
            "Saved index (%d vectors) → %s", self._index.ntotal, settings.faiss_index_path
        )

    def load(self) -> bool:
        """Load index from disk. Returns True on success."""
        idx_path = settings.faiss_index_path
        meta_path = settings.metadata_path

        if not os.path.exists(idx_path) or not os.path.exists(meta_path):
            logger.info("No persisted index found – starting fresh")
            return False

        try:
            self._index = faiss.read_index(idx_path)
            with open(meta_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._metadata = {int(k): v for k, v in raw.items()}
            self._next_id = max(self._metadata.keys(), default=-1) + 1
            self._dim = self._index.d
            logger.info("Loaded index with %d vectors", self._index.ntotal)
            return True
        except Exception as exc:
            logger.error("Failed to load index: %s", exc)
            return False

    def clear(self):
        self._index = None
        self._metadata = {}
        self._next_id = 0
        for path in [settings.faiss_index_path, settings.metadata_path]:
            if os.path.exists(path):
                os.remove(path)
        logger.info("Index cleared")

    @property
    def total_vectors(self) -> int:
        return self._index.ntotal if self._index else 0


# ─── module-level singleton ───────────────────────────────────────────────────
store = FAISSStore()
store.load()          # load from disk if available