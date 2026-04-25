"""
embedding/embedder.py
Thin singleton wrapper around SentenceTransformers.

• Lazy-loads the model on first use.
• Always L2-normalises vectors so that IndexFlatIP == cosine similarity.
• Exposes encode() for both single strings and lists.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Union

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize

from config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    logger.info("Loading embedding model: %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def get_embedding_dim() -> int:
    model = _get_model()
    return model.get_sentence_embedding_dimension()


def encode(
    texts: Union[str, List[str]],
    batch_size: int = 32,
    show_progress: bool = False,
) -> np.ndarray:
    """
    Encode one or more texts → L2-normalised float32 vectors.

    Args:
        texts:         A single string or a list of strings.
        batch_size:    Batch size passed to SentenceTransformer.
        show_progress: Show tqdm progress bar.

    Returns:
        numpy array of shape (n, dim), dtype float32.
    """
    if isinstance(texts, str):
        texts = [texts]

    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
        normalize_embeddings=False,   # we normalise below for explicit control
    )

    embeddings = normalize(embeddings.astype(np.float32))
    return embeddings