"""
api/main.py
FastAPI application.

Endpoints
---------
GET  /          – health check
GET  /status    – index stats
POST /sync-drive – fetch Drive docs, chunk, embed, store
POST /ask        – RAG query
DELETE /clear    – wipe index (dev utility)
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from api.models import AskRequest, AskResponse, SourceItem, StatusResponse, SyncResponse
from config import settings
from connectors.gdrive import fetch_documents
from embedding.embedder import get_embedding_dim
from llm.generator import generate_answer
from processing.chunking import chunk_text
from processing.parser import extract_text
from search.faiss_store import store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ─── app ─────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RAG server starting – index has %d vectors", store.total_vectors)
    yield
    store.save()
    logger.info("Index saved on shutdown")


app = FastAPI(
    title="Highwatch AI – RAG over Google Drive",
    version="1.0.0",
    description="Connect Google Drive, process documents, and answer questions via RAG.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── routes ──────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "RAG API", "version": "1.0.0"}


@app.get("/status", response_model=StatusResponse, tags=["Health"])
def status():
    return StatusResponse(
        total_vectors=store.total_vectors,
        index_loaded=store.total_vectors > 0,
        embedding_model=settings.embedding_model,
    )


@app.post("/sync-drive", response_model=SyncResponse, tags=["Ingestion"])
def sync_drive():
    """
    Fetch all supported files from Google Drive, process them,
    generate embeddings and store in FAISS.

    A full re-sync clears the existing index first.
    """
    t0 = time.perf_counter()
    store.clear()

    files_processed = 0
    total_chunks = 0

    for file_name, mime_type, raw_bytes in fetch_documents():
        text = extract_text(file_name, mime_type, raw_bytes)
        if not text:
            logger.warning("Empty text from %s – skipping", file_name)
            continue

        chunks = chunk_text(text, file_name)
        if not chunks:
            continue

        added = store.add_chunks(chunks)
        total_chunks += added
        files_processed += 1

    store.save()
    elapsed = round(time.perf_counter() - t0, 2)

    return SyncResponse(
        status="success",
        files_processed=files_processed,
        chunks_indexed=total_chunks,
        total_vectors=store.total_vectors,
        message=f"Sync complete in {elapsed}s",
    )


@app.post("/ask", response_model=AskResponse, tags=["Query"])
def ask(request: AskRequest):
    """
    Answer a natural-language question using the indexed documents.
    """
    if store.total_vectors == 0:
        raise HTTPException(
            status_code=400,
            detail="Index is empty. Run POST /sync-drive first.",
        )

    chunks = store.search(
        query=request.query,
        top_k=request.top_k,
        doc_id=request.doc_filter,
    )

    result = generate_answer(request.query, chunks)

    return AskResponse(
        answer=result["answer"],
        sources=[SourceItem(**s) for s in result["sources"]],
        confidence=result["confidence"],
        chunks_used=len(chunks),
    )


@app.delete("/clear", tags=["Dev"])
def clear_index():
    """Wipe the FAISS index and all metadata (dev / re-index utility)."""
    store.clear()
    return {"status": "cleared", "total_vectors": 0}