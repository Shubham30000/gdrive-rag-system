"""
processing/chunking.py
Splits a long text into overlapping word-based chunks with metadata.

Strategy
--------
1. Split on blank lines to respect paragraph / section boundaries.
2. Slide a window of `chunk_size` words across the token stream,
   advancing by (chunk_size - chunk_overlap) words each step.
3. Never emit an empty chunk.

Each chunk is returned as a dict:
    {
        "chunk_id":  int,          # 0-based index within this document
        "text":      str,
        "file_name": str,
        "doc_id":    str,          # same as file_name, for filtering
        "word_count": int,
    }
"""
from __future__ import annotations

import logging
import re
from typing import List, Dict, Any

from config import settings

logger = logging.getLogger(__name__)


def _tokenise(text: str) -> list[str]:
    """Split text into individual word-tokens, preserving punctuation."""
    return text.split()


def _detokenise(tokens: list[str]) -> str:
    return " ".join(tokens)


def chunk_text(
    text: str,
    file_name: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> List[Dict[str, Any]]:
    """
    Chunk `text` into overlapping segments.

    Args:
        text:          Full document text.
        file_name:     Source file name attached to every chunk.
        chunk_size:    Override settings.chunk_size.
        chunk_overlap: Override settings.chunk_overlap.

    Returns:
        List of chunk dicts.
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    if not text.strip():
        logger.warning("Empty text for %s – skipping", file_name)
        return []

    # Step 1: paragraph-aware token list
    paragraphs = re.split(r"\n{2,}", text)
    all_tokens: list[str] = []
    for para in paragraphs:
        tokens = _tokenise(para.strip())
        if tokens:
            all_tokens.extend(tokens)
            # paragraph separator keeps sentence boundary in reconstructed text
            all_tokens.append("\n\n")

    # Remove trailing sentinel
    while all_tokens and all_tokens[-1] == "\n\n":
        all_tokens.pop()

    if not all_tokens:
        return []

    # Step 2: sliding window
    step = max(1, chunk_size - chunk_overlap)
    chunks: List[Dict[str, Any]] = []
    start = 0

    while start < len(all_tokens):
        end = start + chunk_size
        window = all_tokens[start:end]

        # Reconstruct text (collapse the sentinel back to blank line)
        chunk_text_str = _detokenise(window).replace("\n\n ", "\n\n").strip()

        if chunk_text_str:
            chunks.append(
                {
                    "chunk_id": len(chunks),
                    "text": chunk_text_str,
                    "file_name": file_name,
                    "doc_id": file_name,
                    "word_count": len([t for t in window if t != "\n\n"]),
                }
            )

        start += step

    logger.debug("Chunked '%s' → %d chunks", file_name, len(chunks))
    return chunks