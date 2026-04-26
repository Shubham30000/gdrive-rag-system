# 📚 RAG over Google Drive

> **Highwatch AI – Trial Assignment**  
> A production-ready Retrieval-Augmented Generation system that connects to Google Drive,
> processes documents, and answers natural-language questions grounded in your files.

---

## 🎬 Demo Video

> Click the thumbnail below to watch the full project walkthrough

[![RAG over Google Drive – Demo Video](https://img.shields.io/badge/▶%20Watch%20Demo%20Video-Click%20Here-red?style=for-the-badge&logo=youtube)](YOUR_VIDEO_LINK_HERE)



**What the demo covers:**
- Google Drive integration and live document sync
- Chunking and embedding pipeline walkthrough
- 5 live API queries with real responses (including company policy doc)
- Architecture explanation and design decisions

---

## 🔗 Deployed URL

```
https://gdrive-rag-system-1.onrender.com
```

> ⚠️ **Note on deployment:** The app is deployed on Render's free tier. The `/sync-drive` endpoint
> times out on the live server (Render kills requests after 30s; sync takes ~50s for 4 PDFs).
> The pre-built FAISS index is committed to the repository so the server loads 63 vectors on
> startup and `/ask` works correctly. All endpoints are fully functional locally — see the
> demo video for a complete working demonstration.

---

## 🗂️ Document Setup — Google Drive

All documents are stored in a dedicated **`ragdocs`** folder in Google Drive.

```
My Drive/
└── ragdocs/                                          ← GDRIVE_FOLDER_ID points here
    ├── GATE-CS-2025-Set-1-Master-Question-Paper.pdf  (GATE CSE Paper Set 1)
    ├── GATE-CS-2025-Set-2-Master-Question-Paper.pdf  (GATE CSE Paper Set 2)
    ├── GATE-DA-2025-Master-Question-Paper.pdf        (GATE Data Science & AI Paper)
    ├── 23f2005282_DG_T12026.pdf                      (Deep Learning Project Report)
    └── TechNova_Company_Policies.gdoc                (Company Policy Document — Google Doc)
```

**5 files → 63 vectors indexed**

The service account has **Viewer access only** to this folder (least privilege).  
New documents can be added and re-indexed with a single `POST /sync-drive` call locally.

---

## 🏗️ Architecture

```
Google Drive folder (ragdocs/)
        │  all PDFs / Docs / TXT fetched in one API call
        ▼
connectors/gdrive.py
  • Service account auth (Viewer role — least privilege)
  • Lists PDF, Google Docs, TXT — skips unsupported types
  • PDFs → get_media() | Google Docs → export as text/plain
        │
        ▼
processing/parser.py
  • PDF  → PyMuPDF page-by-page text extraction
  • TXT/Docs → UTF-8 / latin-1 decode with fallback
  • Cleans: collapsed whitespace, normalised newlines
        │
        ▼
processing/chunking.py
  • Step 1: split on paragraph breaks (respects semantic units)
  • Step 2: sliding window — 450 words, 75-word overlap
  • Metadata per chunk: file_name, doc_id, chunk_id, word_count
        │
        ▼
embedding/embedder.py
  • Model: all-MiniLM-L6-v2 (384 dimensions, CPU inference)
  • L2-normalised vectors → cosine sim = inner product
  • Batch size 32
        │
        ▼
search/faiss_store.py
  • FAISS IndexFlatIP — exact cosine similarity
  • Persisted: data/faiss.index + data/metadata.json
  • Loads from disk on server startup
        │
   ┌────┴───────────────────────────────────────┐
   │  Query Pipeline                             │
   │  1. Embed query with same model             │
   │  2. FAISS search → top-k × 3 candidates    │
   │  3. Filter chunks below MIN_SCORE (0.25)    │
   │  4. Return top-k with similarity scores     │
   └──────────────────┬──────────────────────────┘
                      ▼
llm/generator.py
  • Prompt: system rules + retrieved context + question
  • AI Pipe → OpenRouter → gpt-4o-mini
  • Returns: answer + source files + confidence score
```

---

## 📁 Project Structure

```
project/
├── api/
│   ├── main.py             FastAPI — routes, lifespan, CORS
│   └── models.py           Pydantic schemas
├── connectors/
│   └── gdrive.py           Google Drive connector
├── embedding/
│   └── embedder.py         SentenceTransformer + normalisation
├── llm/
│   └── generator.py        AI Pipe / gpt-4o-mini
├── processing/
│   ├── chunking.py         Sliding-window chunker
│   └── parser.py           PDF + text extraction
├── search/
│   └── faiss_store.py      FAISS index management
├── tests/
│   └── test_pipeline.py    Unit tests
├── data/
│   ├── faiss.index         Pre-built (committed) — 63 vectors
│   └── metadata.json       Chunk metadata
├── credentials/
│   └── service_account.json   ← never committed
├── config.py
├── .env                    ← never committed
├── .env.example
├── runtime.txt             Python 3.11.9 for Render
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## ⚙️ Local Setup

### Prerequisites
- Python 3.10+
- Google Cloud project with Drive API enabled
- AI Pipe token from [aipipe.org](https://aipipe.org)

### Step 1 — Google Drive Service Account

1. [console.cloud.google.com](https://console.cloud.google.com) → **New Project**
2. **APIs & Services → Library → Google Drive API → Enable**
3. **Credentials → Create Credentials → Service Account** → Role: **Viewer**
4. **Keys → Add Key → JSON** → save as `credentials/service_account.json`
5. Share your Drive folder with the service account email → **Viewer**
6. Copy folder ID from URL: `drive.google.com/drive/folders/`**`FOLDER_ID`**

### Step 2 — Configure `.env`

```bash
cp .env.example .env
```

```env
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json
GDRIVE_FOLDER_ID=your_folder_id_here
AIPIPE_TOKEN=your_aipipe_token_here
EMBEDDING_MODEL=all-MiniLM-L6-v2
FAISS_INDEX_PATH=data/faiss.index
METADATA_PATH=data/metadata.json
CHUNK_SIZE=450
CHUNK_OVERLAP=75
TOP_K=5
MIN_SCORE=0.25
```

### Step 3 — Install & Run

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux

pip install -r requirements.txt

uvicorn api.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** for Swagger UI.

---

## 📡 API Reference

### `GET /` — Health check
```json
{"status": "ok", "service": "RAG API", "version": "1.0.0"}
```

### `GET /status` — Index stats
```json
{"total_vectors": 63, "index_loaded": true, "embedding_model": "all-MiniLM-L6-v2"}
```

### `POST /sync-drive` — Index all Drive files
> Run locally. Fetches all files, chunks, embeds, saves to `data/`.
```json
{
  "status": "success",
  "files_processed": 5,
  "chunks_indexed": 63,
  "total_vectors": 63,
  "message": "Sync complete in 52.4s"
}
```

### `POST /ask` — Ask a question

**Request:**
```json
{
  "query": "What is the refund policy at TechNova Solutions?",
  "top_k": 5,
  "doc_filter": "TechNova_Company_Policies.gdoc"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | ✅ | Your question |
| `top_k` | int | ❌ | Chunks to retrieve (default 5) |
| `doc_filter` | string | ❌ | Restrict to one specific file |

**Response:**
```json
{
  "answer": "TechNova Solutions offers a 30-day money-back guarantee for all new annual subscriptions. Refund requests must be submitted in writing to billing@technovasolutions.com within 30 days of the initial purchase. After the 30-day window, partial refunds may be granted on a pro-rata basis only for verified service outages or unresolved product defects.",
  "sources": [
    {
      "file": "TechNova_Company_Policies.gdoc",
      "chunk": "TechNova offers a 30-day money-back guarantee for all new annual subscriptions..."
    }
  ],
  "confidence": 0.6341,
  "chunks_used": 3
}
```

### `DELETE /clear` — Wipe index (dev only)

---

## 🧪 Sample Queries & Real Outputs

### Company Policy Document

```cmd
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"query\": \"What is the refund policy at TechNova Solutions?\"}"
```
```cmd
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"query\": \"How many days of annual leave do employees get?\"}"
```
```cmd
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"query\": \"What are the remote work rules at TechNova?\"}"
```

### Deep Learning Report

```cmd
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"query\": \"What models were used in the music genre classification project?\"}"
```
**Sample output:**
```json
{
  "answer": "Three model families were used: (1) Classical ML baseline — MFCC features with LightGBM; (2) Custom AttentionCRNN — CNN + Bidirectional GRU + attention pooling; (3) Fine-tuned transformers — Wav2Vec2-base and Audio Spectrogram Transformer (AST) pretrained on AudioSet. The AST achieved a validation Macro F1 of 0.8828.",
  "sources": [{"file": "23f2005282_DG_T12026.pdf", "chunk": "..."}],
  "confidence": 0.5261,
  "chunks_used": 5
}
```

### GATE Papers — Cross-document Retrieval

```cmd
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"query\": \"List the subjects and question types in GATE CS 2025\"}"
```
**Sample output:**
```json
{
  "answer": "GATE CS 2025 includes: General Aptitude (Q1–Q5: 1 mark, Q6–Q10: 2 marks) and Computer Science core sections covering algorithms, data structures, OS, DBMS, computer networks, and theory of computation. Question types include MCQ, MSQ, and Numerical Answer Type (NAT).",
  "sources": [
    {"file": "GATE-DA-2025-Master-Question-Paper.pdf", "chunk": "..."},
    {"file": "GATE-CS-2025-Set-1-Master-Question-Paper.pdf", "chunk": "..."},
    {"file": "GATE-CS-2025-Set-2-Master-Question-Paper.pdf", "chunk": "..."}
  ],
  "confidence": 0.278,
  "chunks_used": 4
}
```

---

## 🚀 Deployment

Deployed on **Render** free tier: `https://gdrive-rag-system-1.onrender.com`

The pre-built FAISS index (`data/`) is committed to the repo so the server loads 63 vectors instantly on startup without needing `/sync-drive`.

**Adding new documents workflow:**
```
1. Upload file to ragdocs folder in Google Drive
2. Run locally: curl -X POST http://localhost:8000/sync-drive
3. git add data/ && git commit -m "Update index" && git push
4. Render auto-redeploys with fresh index
```

---

## 🧠 Design Decisions

| Component | Choice | Reasoning |
|---|---|---|
| Vector store | FAISS `IndexFlatIP` | Exact cosine similarity after L2-norm, zero infrastructure |
| Embeddings | `all-MiniLM-L6-v2` | 384-dim, fast CPU, strong retrieval quality |
| Chunking | Paragraph-aware sliding window | Respects semantic boundaries; overlap avoids split context |
| LLM | AI Pipe → gpt-4o-mini | Large context window, reliable, OpenAI-compatible |
| No LangChain | Direct implementation | Full control, transparent pipeline, minimal dependencies |
| Drive auth | Service account | Server-side, no user OAuth flow required |
| Pre-built index | Committed `data/` | Avoids Render 512MB OOM and 30s timeout on free tier |

---

## ✅ Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## 📌 Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/status` | Index stats |
| `POST` | `/sync-drive` | Fetch + index all Drive files |
| `POST` | `/ask` | Ask a question |
| `DELETE` | `/clear` | Wipe index |
