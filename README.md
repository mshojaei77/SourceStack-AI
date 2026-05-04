# SourceStack AI

SourceStack AI now runs primarily as:

- `frontend/`: React + Vite + TypeScript UI
- `backend/`: FastAPI API layer
- `src/research_assistant/`: existing Python RAG engine (kept as backend brain)

Streamlit is still kept as a legacy/debug fallback (`src/app.py`) while React stabilizes.

## Architecture

```text
React/Vite frontend
  -> HTTP + SSE
FastAPI backend
  -> existing research_assistant modules
Qdrant + SearxNG + LLM + embeddings + reranker
```

## Core Routes

- Frontend:
  - `/chat`
  - `/sources`
  - `/reports`
  - `/settings`
- API:
  - `/api/workbases...`
  - `/api/chats/...`
  - `/api/sources/...`
  - `/api/reports/...`
  - `/api/exports/markdown`
  - `/api/exports/pdf`
  - `/api/settings`

## Docker Stack (Recommended)

The Compose stack now includes:

- `frontend` (Vite dev server)
- `backend` (FastAPI)
- `qdrant`
- `searxng`

### 1. Configure `.env`

At minimum, set your model/provider keys in `.env` (example):

```env
OPENROUTER_API_KEY=...
GENERATION_MODEL=...
EMBEDDING_MODEL=...
```

### 2. Start Full Stack

```powershell
docker compose up --build
```

### 3. Open

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/api/health`
- Qdrant: `http://localhost:6333`
- SearxNG: `http://localhost:8080`

## Local Run (Without Dockerized App Services)

1. Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

2. Install frontend dependencies:

```powershell
cd frontend
npm install
cd ..
```

3. Start infra only:

```powershell
docker compose up -d qdrant searxng
```

4. Start backend:

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

5. Start frontend:

```powershell
cd frontend
npm run dev
```

## Legacy Streamlit Fallback

Keep Streamlit available for debugging:

```powershell
python -m streamlit run src/app.py --server.port=8502
```

## Chat Export Workflow

In Chat and the right Control Panel Export tab:

- Export selected assistant answer to Markdown
- Export selected assistant answer to PDF
- Save selected assistant answer as Report
- Reports page supports Markdown/PDF export for saved reports
- Exports include citations/references/source list via backend export builder

## Integration Smoke Checks

Run end-to-end API checks:

```powershell
python scripts/integration_checks.py
```

Checks performed:

1. Create Workbase
2. Upload source
3. Ask question with streaming
4. Receive citations
5. Save report
6. Export Markdown
7. Export PDF (skips gracefully if Pandoc is unavailable)
8. Cleanup test Workbase

## Notes

- PDF export requires Pandoc on the backend host/container.
- SSE streaming endpoint: `POST /api/chats/{chat_id}/messages/stream`
- Streamlit code remains in repo intentionally until React parity is complete.
