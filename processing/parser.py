"""
processing/parser.py
Converts raw file bytes into clean plain text.

Supported:
  • PDF  → via PyMuPDF (fitz)
  • text/plain  → direct decode
  • Google Docs exported as text/plain → same as above
"""
from __future__ import annotations

import io
import logging
import re
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Normalise whitespace while preserving paragraph boundaries."""
    # Collapse runs of spaces / tabs on a single line
    text = re.sub(r"[ \t]+", " ", text)
    # Three or more newlines → two (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove lines that are only whitespace
    lines = [ln.rstrip() for ln in text.splitlines()]
    text = "\n".join(lines)
    return text.strip()


# ─── parsers ─────────────────────────────────────────────────────────────────

def parse_pdf(raw_bytes: bytes) -> str:
    """Extract text from a PDF using PyMuPDF."""
    pages: list[str] = []
    with fitz.open(stream=raw_bytes, filetype="pdf") as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    return _clean("\n\n".join(pages))


def parse_plain_text(raw_bytes: bytes) -> str:
    """Decode bytes to string (handles common encodings)."""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return _clean(raw_bytes.decode(enc))
        except UnicodeDecodeError:
            continue
    # last resort
    return _clean(raw_bytes.decode("utf-8", errors="replace"))


# ─── public interface ─────────────────────────────────────────────────────────

def extract_text(file_name: str, mime_type: str, raw_bytes: bytes) -> str:
    """
    Route raw bytes to the correct parser.

    Args:
        file_name:  original file name (used for logging / fallback routing)
        mime_type:  MIME string from Google Drive
        raw_bytes:  raw file content

    Returns:
        Cleaned plain-text string.  Empty string if extraction fails.
    """
    try:
        if mime_type == "application/pdf" or file_name.lower().endswith(".pdf"):
            return parse_pdf(raw_bytes)
        else:
            # Google Docs (already exported as text/plain) and .txt files
            return parse_plain_text(raw_bytes)
    except Exception as exc:
        logger.error("Text extraction failed for %s: %s", file_name, exc)
        return ""