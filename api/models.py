"""
api/models.py
Pydantic schemas for request and response bodies.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ─── /sync-drive ─────────────────────────────────────────────────────────────

class SyncResponse(BaseModel):
    status: str
    files_processed: int
    chunks_indexed: int
    total_vectors: int
    message: str


# ─── /ask ────────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000, description="User question")
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    doc_filter: Optional[str] = Field(default=None, description="Restrict to a specific file name")


class SourceItem(BaseModel):
    file: str
    chunk: str


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    confidence: float
    chunks_used: int


# ─── /status ─────────────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    total_vectors: int
    index_loaded: bool
    embedding_model: str