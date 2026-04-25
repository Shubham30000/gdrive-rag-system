"""
llm/generator.py
Generates grounded answers using AI Pipe (https://aipipe.org)
which proxies OpenRouter — OpenAI-compatible API.

Set AIPIPE_TOKEN in your .env file.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from config import settings

logger = logging.getLogger(__name__)

AIPIPE_URL = "https://aipipe.org/openrouter/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"   # cheap, fast, good quality on free tier

_PROMPT_TEMPLATE = """\
You are a helpful assistant that answers questions strictly based on the \
provided context.

Rules:
- Answer ONLY from the context below. Do not use external knowledge.
- If the context does not contain enough information, say so clearly.
- Keep your answer under 300 words.
- Be concise, accurate, and professional.

Context:
{context}

Question: {question}

Answer:"""


def _build_context(chunks: List[Dict[str, Any]]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        src = chunk.get("file_name", "unknown")
        parts.append(f"[Source {i}: {src}]\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)


def generate_answer(
    query: str,
    chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not chunks:
        return {
            "answer": "I could not find relevant information in the documents to answer your question.",
            "sources": [],
            "confidence": 0.0,
        }

    context = _build_context(chunks)
    prompt = _PROMPT_TEMPLATE.format(context=context, question=query)

    # De-duplicate sources while preserving order
    seen: set[str] = set()
    sources = []
    for c in chunks:
        fn = c.get("file_name", "unknown")
        if fn not in seen:
            seen.add(fn)
            sources.append({"file": fn, "chunk": c["text"][:200] + "…"})

    confidence = float(max((c.get("score", 0.0) for c in chunks), default=0.0))

    # ── AI Pipe call ─────────────────────────────────────────────────────────
    if not settings.aipipe_token:
        logger.warning("AIPIPE_TOKEN not set – returning stub answer")
        return {
            "answer": (
                "[DEMO MODE – set AIPIPE_TOKEN in .env]\n\n"
                "Retrieved context:\n\n" + context[:800]
            ),
            "sources": sources,
            "confidence": confidence,
        }

    answer = "LLM call failed: unknown error"

    try:
        response = httpx.post(
            AIPIPE_URL,
            headers={
                "Authorization": f"Bearer {settings.aipipe_token}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.2,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()
        logger.info("AI Pipe response received, model=%s", MODEL)

    except httpx.HTTPStatusError as exc:
        logger.error("AI Pipe HTTP error %s: %s", exc.response.status_code, exc.response.text)
        answer = f"LLM call failed: HTTP {exc.response.status_code} – {exc.response.text[:200]}"
    except Exception as exc:
        logger.error("AI Pipe error: %s", exc)
        answer = f"LLM call failed: {exc}"

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }