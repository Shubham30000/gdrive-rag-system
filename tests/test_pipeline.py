"""
tests/test_pipeline.py
Unit tests that run without Google Drive or a real LLM.
"""
import pytest
from processing.chunking import chunk_text
from processing.parser import _clean


# ─── parser ──────────────────────────────────────────────────────────────────

def test_clean_removes_extra_whitespace():
    raw = "hello   world\n\n\n\n\nfoo"
    cleaned = _clean(raw)
    assert "   " not in cleaned
    assert cleaned.count("\n\n") <= 1 or "\n\n\n" not in cleaned


def test_clean_strips():
    assert _clean("  hello  ").startswith("hello")


# ─── chunker ─────────────────────────────────────────────────────────────────

SAMPLE = (
    "The refund policy states that customers may request a full refund within 30 days "
    "of purchase. After 30 days, only store credit is available. Products must be returned "
    "in original condition.\n\n"
    "Our data privacy policy requires that all user data be stored securely and never sold "
    "to third parties. Users may request data deletion at any time by contacting support.\n\n"
    "The onboarding process involves three steps: account creation, identity verification, "
    "and initial configuration. This process typically takes 15 minutes."
) * 10  # repeat to generate enough tokens


def test_chunk_returns_list():
    chunks = chunk_text(SAMPLE, "test.pdf")
    assert isinstance(chunks, list)
    assert len(chunks) > 0


def test_chunk_has_required_keys():
    chunks = chunk_text(SAMPLE, "test.pdf")
    required = {"chunk_id", "text", "file_name", "doc_id", "word_count"}
    for c in chunks:
        assert required.issubset(c.keys()), f"Missing keys in chunk: {c.keys()}"


def test_chunk_ids_are_sequential():
    chunks = chunk_text(SAMPLE, "test.pdf")
    for i, c in enumerate(chunks):
        assert c["chunk_id"] == i


def test_chunk_file_name_propagated():
    chunks = chunk_text(SAMPLE, "policy.pdf")
    for c in chunks:
        assert c["file_name"] == "policy.pdf"


def test_empty_text_returns_empty_list():
    assert chunk_text("", "empty.txt") == []
    assert chunk_text("   \n  ", "blank.txt") == []


def test_custom_chunk_size():
    chunks = chunk_text(SAMPLE, "test.pdf", chunk_size=100, chunk_overlap=20)
    for c in chunks:
        assert c["word_count"] <= 110  # slight tolerance for sentence tokens


# ─── embedder (integration, requires model download) ─────────────────────────

def test_encode_single_string():
    pytest.importorskip("sentence_transformers")
    from embedding.embedder import encode
    vec = encode("What is the refund policy?")
    assert vec.shape[0] == 1
    assert vec.shape[1] > 0


def test_encode_normalised():
    pytest.importorskip("sentence_transformers")
    import numpy as np
    from embedding.embedder import encode
    vec = encode(["hello world"])
    norm = np.linalg.norm(vec[0])
    assert abs(norm - 1.0) < 1e-5, f"Vector not normalised: norm={norm}"