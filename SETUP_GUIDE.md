# Setup Guide

This guide walks you through setting up S5-HES Agent from scratch.

## 1. System Requirements

| Component | Minimum Version |
|-----------|----------------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |
| Git | 2.30+ |
| Disk space | ~2 GB (including downloaded assets) |

**LLM Provider** (choose one):
- **Ollama** (recommended for local inference) — [Install Ollama](https://ollama.ai/)
- **OpenAI** — Requires API key from [platform.openai.com](https://platform.openai.com/api-keys)
- **Google Gemini** — Requires API key from [aistudio.google.com](https://aistudio.google.com/apikey)

## 2. Clone the Repository

```bash
git clone https://github.com/AsiriweLab/S5-HES-Agent.git
cd S5-HES-Agent
```

## 3. Download Large Assets

The ChromaDB vector database (~410 MB) and embedding models (~1.4 GB) are hosted on Google Drive due to their size.

**Download link:** [S5-HES Agent Assets](https://drive.google.com/drive/folders/14X84lTTI11kM-mB5Vx0QqfsTmp7qFZFi?usp=sharing)

After downloading, place the files as follows:

```
S5-HES-Agent/
├── backend/
│   └── chroma_data/          ← Extract ChromaDB data here
├── models/
│   └── embeddings/           ← Extract embedding model weights here
```

Alternatively, use the download script:

```bash
cd backend
python scripts/download_models.py
```

## 4. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

# Install dependencies
pip install -e .

# For development tools (pytest, ruff, mypy):
pip install -e ".[dev]"
```

### Configure Environment

```bash
cp .env.example .env
```

Edit `.env` to configure your LLM provider:

**Option A: Ollama (local, no API key needed)**
```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M
```

Make sure Ollama is running and the model is pulled:
```bash
ollama pull llama3.1:8b-instruct-q4_K_M
```

**Option B: OpenAI**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
```

**Option C: Google Gemini**
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash
```

### Start the Backend

```bash
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at `http://localhost:8000`. Interactive API documentation is at `http://localhost:8000/docs`.

## 5. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The web interface will be available at `http://localhost:5173`.

## 6. Rebuilding the Knowledge Base (Optional)

If you have access to the academic papers listed in `knowledge_base/paper_manifest.yaml`, you can rebuild the knowledge base from scratch:

1. Place the PDF files in the appropriate `knowledge_base/` subdirectories
2. Run the ingestion script:

```bash
python knowledge_base/scripts/organize_and_ingest.py
```

This will process the documents, generate embeddings, and populate the ChromaDB vector store.

## 7. Running Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test categories
pytest tests/integration/
pytest tests/e2e/
pytest tests/performance/
```

## 8. Troubleshooting

| Issue | Solution |
|-------|---------|
| ChromaDB errors on startup | Ensure `chroma_data/` is downloaded and placed in `backend/` |
| Embedding model not found | Download models from Google Drive or run `python scripts/download_models.py` |
| Ollama connection refused | Start Ollama (`ollama serve`) and pull the model first |
| Frontend can't reach backend | Check CORS settings in `.env` and ensure backend is running on port 8000 |
| Import errors | Ensure you installed with `pip install -e .` from the `backend/` directory |
