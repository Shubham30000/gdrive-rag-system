# 📚 RAG over Google Drive

> **Highwatch AI – Trial Assignment**  
> A production-ready Retrieval-Augmented Generation system that connects to Google Drive,
> processes documents, and answers natural-language questions grounded in your files.

---

## 🔗 Live Demo

```
Base URL: https://gdrive-rag-system-1.onrender.com
```

| | URL |
|---|---|
| 🟢 Health check | https://gdrive-rag-system-1.onrender.com/ |
| 📖 Swagger UI (interactive) | https://gdrive-rag-system-1.onrender.com/docs |
| 📊 Index status | https://gdrive-rag-system-1.onrender.com/status |

> 💤 **Note:** Hosted on Render free tier — first request after inactivity takes ~30s to wake up.
> After waking, call `/sync-drive` once before asking questions (index lives in memory).

---

## 🗂️ My Approach — Document Organization

All documents to be indexed are uploaded to a **dedicated Google Drive folder** called `ragdocs`.

```
My Drive/
└── ragdocs/                        ← GDRIVE_FOLDER_ID points here
    ├── GATE-CS-2025-Set-1-Master-Question-Paper.pdf
    ├── GATE-CS-2025-Set-2-Master-Question-Paper.pdf
    ├── GATE-DA-2025-Master-Question-Paper.pdf
    └── 23f2005282_DG_T12026.pdf
```

**Why a dedicated folder?**
- The service account is granted **Viewer access only on this folder** — not the entire Drive.
  This follows the principle of least privilege and keeps credentials safe.
- New documents can be added to the folder and re-indexed with a single `POST /sync-drive` call.
- The `GDRIVE_FOLDER_ID` env var points to this folder's ID (extracted from its Drive URL).
- Leaving `GDRIVE_FOLDER_ID` empty would search the entire Drive — useful for broader use cases.

**Sync behaviour:**
- `POST /sync-drive` fetches **all** files from the folder in one pass, processes them in sequence,
  and rebuilds the FAISS index from scratch. 55 vectors were indexed from 4 PDFs.

---

## 🏗️ Architecture

```
Google Drive folder (ragdocs/)
        │  all PDFs / Docs / TXT fetched in one API call
        ▼
connectors/gdrive.py
  • Authenticates via service account JSON
  • Lists all supported files (PDF, Google Docs, TXT) in the folder
  • Downloads each file — PDFs via get_media(), Docs exported as text/plain
        │
        ▼
processing/parser.py
  • PDF  → PyMuPDF (fitz) extracts text page by page
  • TXT / Google Docs → decoded with UTF-8 / latin-1 fallback
  • Text cleaned: collapsed whitespace, normalised newlines
        │
        ▼
processing/chunking.py
  • Splits on paragraph breaks first (respects semantic boundaries)
  • Sliding window: chunk_size=450 words, overlap=75 words
  • Each chunk carries metadata: file_name, doc_id, chunk_id, word_count
        │
        ▼
embedding/embedder.py
  • Model: sentence-transformers/all-MiniLM-L6-v2  (384 dimensions)
  • Vectors L2-normalised → cosine similarity = inner product
  • Batch size 32, runs on CPU
        │
        ▼
search/faiss_store.py
  • FAISS IndexFlatIP — exact cosine similarity (no approximation)
  • Index + metadata persisted to data/faiss.index + data/metadata.json
  • Loaded from disk on server startup
        │
   ┌────┴─────────────────────────────────────────┐
   │  Query Pipeline                               │
   │  1. Embed query with same model               │
   │  2. FAISS search → top-k × 3 candidates      │
   │  3. Filter: score ≥ MIN_SCORE (0.25)          │
   │  4. Return top-k chunks with scores           │
   └────────────────────┬─────────────────────────┘
                        ▼
llm/generator.py
  • Builds prompt: system rules + retrieved context + question
  • Calls AI Pipe → OpenRouter → gpt-4o-mini
  • Returns: answer (≤300 words) + source files + confidence score
```

---

## 📁 Project Structure

```
project/
├── api/
│   ├── main.py             FastAPI app — routes, lifespan, CORS
│   └── models.py           Pydantic request/response schemas
├── connectors/
│   └── gdrive.py           Google Drive connector
├── embedding/
│   └── embedder.py         SentenceTransformer + L2 normalisation
├── llm/
│   └── generator.py        AI Pipe / gpt-4o-mini answer generation
├── processing/
│   ├── chunking.py         Paragraph-aware sliding-window chunker
│   └── parser.py           PDF + text extraction and cleaning
├── search/
│   └── faiss_store.py      FAISS index — add, search, save, load, clear
├── tests/
│   └── test_pipeline.py    Unit tests (no Drive / LLM needed)
├── credentials/
│   └── service_account.json   ← never committed
├── data/                   Auto-created: faiss.index + metadata.json
├── config.py               Central settings via pydantic-settings
├── .env                    ← secrets, never committed
├── .env.example            Safe template
├── runtime.txt             Pins Python 3.11.9 for Render
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## 🖥️ How to Use — Swagger UI (Step by Step)

The easiest way to test the API without any curl commands.

**Open:** https://gdrive-rag-system-1.onrender.com/docs

You will see a list of all endpoints. Here's how to use each one:

### Step 1 — Sync Google Drive

1. Click on **`POST /sync-drive`** to expand it
2. Click the **"Try it out"** button (top right of that section)
3. Click the blue **"Execute"** button
4. Wait ~30–60 seconds — it fetches, chunks and embeds all your Drive files
5. You will see the response below:
```json
{
  "status": "success",
  "files_processed": 4,
  "chunks_indexed": 55,
  "total_vectors": 55,
  "message": "Sync complete in 50.93s"
}
```

### Step 2 — Ask a Question

1. Click on **`POST /ask`** to expand it
2. Click **"Try it out"**
3. In the **Request body** box, edit the JSON:
```json
{
  "query": "List the subjects and question types in GATE CS 2025"
}
```
4. Click **"Execute"**
5. Response appears below with `answer`, `sources`, and `confidence`

**Optional fields you can add:**
```json
{
  "query": "What algorithms are tested?",
  "top_k": 5,
  "doc_filter": "GATE-CS-2025-Set-1-Master-Question-Paper.pdf"
}
```
- `top_k` — how many chunks to retrieve (default 5)
- `doc_filter` — limit search to one specific file

### Step 3 — Check Status

1. Click **`GET /status`** → **"Try it out"** → **"Execute"**
2. See how many vectors are currently indexed

---

## ⚙️ Local Setup

### Prerequisites
- Python 3.10+
- Google Cloud project with Drive API enabled
- AI Pipe token from [aipipe.org](https://aipipe.org)

### Step 1 — Google Drive Service Account

1. [console.cloud.google.com](https://console.cloud.google.com) → **New Project**
2. **APIs & Services → Library** → **Google Drive API** → **Enable**
3. **Credentials → Create Credentials → Service Account** → Role: **Viewer**
4. **Keys tab → Add Key → JSON** → save as `credentials/service_account.json`
5. Copy the service account email
6. In Google Drive → right-click your folder → **Share** → paste email → **Viewer**
7. Copy folder ID from URL: `drive.google.com/drive/folders/`**`FOLDER_ID_HERE`**

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

Open **http://localhost:8000/docs**

---

## 📡 API Reference

### `GET /` — Health check
```json
{"status": "ok", "service": "RAG API", "version": "1.0.0"}
```

### `GET /status` — Index stats
```json
{"total_vectors": 55, "index_loaded": true, "embedding_model": "all-MiniLM-L6-v2"}
```

### `POST /sync-drive` — Index all Drive files
```json
{
  "status": "success",
  "files_processed": 4,
  "chunks_indexed": 55,
  "total_vectors": 55,
  "message": "Sync complete in 50.93s"
}
```

### `POST /ask` — Ask a question

**Request:**
```json
{
  "query": "List the subjects and question types in GATE CS 2025",
  "top_k": 5,
  "doc_filter": "GATE-CS-2025-Set-1-Master-Question-Paper.pdf"
}
```

**Response:**
```json
{
  "answer": "The GATE CS 2025 paper includes: General Aptitude (Q1–Q5, 1 mark; Q6–Q10, 2 marks), and Computer Science core questions covering algorithms, data structures, OS, DBMS, computer networks, and theory of computation...",
  "sources": [
    {
      "file": "GATE-CS-2025-Set-1-Master-Question-Paper.pdf",
      "chunk": "Computer Science and Information Technology (CS1) Organising Institute: IIT Roorkee..."
    }
  ],
  "confidence": 0.278,
  "chunks_used": 4
}
```

### `DELETE /clear` — Wipe index (dev only)

---

## 🧪 Sample Queries

**Windows cmd — single line only:**
```cmd
curl -X POST https://gdrive-rag-system-1.onrender.com/sync-drive

curl -X POST https://gdrive-rag-system-1.onrender.com/ask -H "Content-Type: application/json" -d "{\"query\": \"List the subjects and question types in GATE CS 2025\"}"

curl -X POST https://gdrive-rag-system-1.onrender.com/ask -H "Content-Type: application/json" -d "{\"query\": \"What algorithms are covered in GATE CS Set 2?\"}"

curl -X POST https://gdrive-rag-system-1.onrender.com/ask -H "Content-Type: application/json" -d "{\"query\": \"What is the marking scheme?\", \"doc_filter\": \"GATE-DA-2025-Master-Question-Paper.pdf\"}"
```

**Mac/Linux:**
```bash
curl -X POST https://gdrive-rag-system-1.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "List the subjects and question types in GATE CS 2025"}'
```

---

## 🚀 Deployment (Render)

### 1 — `.gitignore`
```
.env
.venv/
__pycache__/
*.pyc
data/
credentials/
```

### 2 — Push to GitHub
```bash
git init
git add .
git commit -m "RAG over Google Drive"
git remote add origin https://github.com/YOUR_USERNAME/rag-gdrive.git
git push -u origin main
```

### 3 — Render settings

| Field | Value |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |

### 4 — Environment variables (Render → Environment tab)

| Key | Value |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `service_account.json` |
| `GDRIVE_FOLDER_ID` | your folder ID |
| `AIPIPE_TOKEN` | your token |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` |
| `FAISS_INDEX_PATH` | `data/faiss.index` |
| `METADATA_PATH` | `data/metadata.json` |
| `CHUNK_SIZE` | `450` |
| `CHUNK_OVERLAP` | `75` |
| `TOP_K` | `5` |
| `MIN_SCORE` | `0.25` |

### Step 5 — Add the Service Account JSON

Since `credentials/` is not committed, use Render's Secret Files:

1. Render → your service → **Secret Files** tab
2. **Add Secret File**
   - **Filename:** `service_account.json`
   - **Contents:** paste the full JSON from your local `service_account.json`
3. Save

### Step 6 — Deploy

Click **Deploy Service**. Build takes ~3 minutes.

> ⚠️ **After deploy — update the URL at the top of this file.**  
> Replace `https://<YOUR-RENDER-APP-NAME>.onrender.com` with your real Render URL.
> You can find it in the Render dashboard under your service name.

### Step 7 — Sync and Test

```bash
curl -X POST https://gdrive-rag-system-1.onrender.com/sync-drive
```

---

## 🐳 Docker

```bash
docker-compose up --build
docker-compose down
```

---

## 🧠 Design Decisions

| Component | Choice | Reasoning |
|---|---|---|
| Vector store | FAISS `IndexFlatIP` | Exact cosine sim after L2-norm, zero infra |
| Embeddings | `all-MiniLM-L6-v2` | 384-dim, fast CPU, strong retrieval quality |
| Chunking | Paragraph-aware sliding window | Respects semantic boundaries, overlap avoids split context |
| LLM | AI Pipe → gpt-4o-mini | OpenAI-compatible proxy, large context window, reliable |
| No LangChain | Direct implementation | Full control, minimal deps, transparent pipeline |
| Drive auth | Service account (not OAuth) | Server-side, no user login flow needed |

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
| `DELETE` | `/clear` | Wipe index (dev only) |