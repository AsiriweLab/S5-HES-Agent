# S5-HES Agent

**Society 5.0-driven Agentic Framework for Smart Home Environment Simulation**

S5-HES Agent is a research framework that combines agentic AI orchestration with retrieval-augmented generation (RAG) to simulate realistic smart home environments and analyze their security posture. Built for reproducible IoT security research, it integrates multi-provider LLM support, hybrid semantic search, behavioral device simulation, and MITRE ATT&CK-aligned threat modeling into a unified platform.

## Key Features

- **Agentic RAG Pipeline** — Multi-stage retrieval with hybrid semantic/keyword search, anti-hallucination verification, and source-grounded responses backed by a domain-specific knowledge base
- **Smart Home Simulation** — Realistic device behavior modeling with configurable home layouts, occupant activity patterns, and IoT protocol simulation (Zigbee, Z-Wave, Wi-Fi, Matter)
- **Threat Scenario Engine** — MITRE ATT&CK-mapped threat simulation covering reconnaissance, initial access, lateral movement, and data exfiltration across smart home attack surfaces
- **Multi-Provider LLM Support** — Seamless switching between Ollama (local), OpenAI, and Google Gemini with unified prompt management and response verification
- **Interactive Web Interface** — Vue.js dashboard for simulation control, threat visualization, knowledge base exploration, and experiment management

## Architecture

S5-HES Agent follows a three-layer architecture:

1. **Presentation Layer** — Vue 3 + TypeScript frontend with real-time simulation dashboards, attack chain visualization, and administrative controls
2. **Application Layer** — FastAPI backend with agentic AI orchestration, RAG pipeline (ChromaDB + sentence-transformers), simulation engine, and security analysis modules
3. **Data Layer** — ChromaDB vector store for knowledge retrieval, MITRE ATT&CK Enterprise framework data, and configurable device/scenario definitions

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.ai/) (for local LLM inference) or OpenAI/Gemini API key

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env to set your LLM provider and API keys

# Start the backend server
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The application will be available at `http://localhost:5173` (frontend) and `http://localhost:8000` (API).

### Large Assets (Required)

The ChromaDB vector database and embedding models are too large for Git. Download them from Google Drive:

**[Download S5-HES Agent Assets](https://drive.google.com/drive/folders/14X84lTTI11kM-mB5Vx0QqfsTmp7qFZFi?usp=sharing)**

After downloading:
- Extract `chroma_data/` into `backend/chroma_data/`
- Extract `models/` into `models/embeddings/`

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions.

## Knowledge Base

The knowledge base was constructed from academic papers, device specifications, and threat intelligence sources. Due to copyright restrictions, the original documents are **not redistributed** in this repository.

The references are listed in `knowledge_base/paper_manifest.yaml`. Researchers can obtain these publications from their respective publishers (IEEE Xplore, ACM Digital Library, arXiv, etc.) and rebuild the knowledge base using:

```bash
python knowledge_base/scripts/organize_and_ingest.py
```

## Project Structure

```
S5-HES-Agent/
├── backend/
│   ├── src/
│   │   ├── ai/            # LLM providers, agents, orchestrator, verification
│   │   ├── api/           # FastAPI routes and endpoints
│   │   ├── core/          # Configuration, models, settings
│   │   ├── iot/           # IoT protocols (Zigbee, Z-Wave, Wi-Fi, Matter)
│   │   ├── rag/           # RAG pipeline (retriever, embeddings, vector store)
│   │   ├── security/      # Security analysis and code review
│   │   └── simulation/    # Device behavior, home layout, threat scenarios
│   ├── tests/             # Unit, integration, e2e, performance tests
│   ├── scripts/           # Utility scripts (model download, migration)
│   └── knowledge_base/    # MITRE ATT&CK Enterprise data
├── frontend/
│   └── src/
│       ├── components/    # Vue 3 UI components
│       ├── views/         # Page views (Dashboard, Simulation, Threats, etc.)
│       ├── stores/        # Pinia state management
│       └── services/      # API client services
├── data/                  # Application fixtures and admin defaults
├── knowledge_base/        # Paper manifest, detection patterns, ingestion scripts
└── models/                # Embedding model weights (download from Google Drive)
```

## Citation

If you use S5-HES Agent in your research, please cite:

pending.

<! --
```bibtex
@article{s5hes2026,
  title     = {S5-HES Agent: A Society 5.0-driven Agentic Framework for Smart Home Environment Simulation},
  author    = {Smart-HES Research Team},
  journal   = {IEEE Open Journal of Computer Science},
  year      = {2026},
  note      = {Under review},
  url       = {https://github.com/AsiriweLab/S5-HES-Agent}
}
```
-->

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
