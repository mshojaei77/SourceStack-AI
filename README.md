# Research Assistant

An open-source, agentic RAG chatbot with incremental web knowledge ingestion.

This project creates isolated `Workbases` (project-specific knowledge spaces).  
For each user question, the system:

1. Uses LLM tool calling to trigger `search_web` (SearxNG).
2. Scrapes returned pages (with fallbacks).
3. Chunks + embeds content and upserts it into Qdrant for the active Workbase.
4. Retrieves from the full accumulated Workbase history.
5. Reranks retrieved chunks.
6. Generates a grounded answer with sources.

The result is a continuously growing, per-Workbase knowledge base.

## Key Features

- Incremental RAG ingestion per question.
- Strict Workbase data isolation in Qdrant using metadata filtering.
- LangGraph orchestration for ingestion and retrieval flow.
- Reranker integration for higher-quality context selection.
- Streamlit UI + CLI interface sharing the same backend pipeline.
- Dataset iteration tracking (`dataset-000001`, `dataset-000002`, ...).
- Scrape failure tracking with snippet fallback.

## Architecture

Core flow:

1. `plan_search` (LLM tool calling for search query)
2. `search_web` (SearxNG API)
3. `ingest_dataset` (scrape, chunk, embed, upsert)
4. `retrieve_workbase` (semantic retrieval + rerank)
5. final generation (grounded response with citations)

Stack:

- LLM + embeddings: OpenAI-compatible endpoint via OpenRouter or local server
- Orchestration: LangGraph
- Vector DB: Qdrant
- Search: Self-hosted SearxNG
- Scraping: Trafilatura + BeautifulSoup + optional Playwright
- UI: Streamlit
- CLI: `argparse`-based utility for direct testing

## Project Structure

```text
.
|- config/
|  `- searxng/
|     `- settings.yml
|- data/
|  `- workspaces/
|- docs/
|  |- cli.md
|  |- milestones.md
|  `- vector_schema.md
|- src/
|  |- app.py
|  |- cli.py
|  `- research_assistant/
|     |- config.py
|     |- llm.py
|     |- rag_pipeline.py
|     |- reranker.py
|     |- search.py
|     |- text.py
|     |- vector_store.py
|     `- workbases.py
|- docker-compose.yml
`- requirements.txt
```

## Quickstart

### 1. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 2. Start infrastructure

```powershell
docker compose up -d
```

This starts:

- `qdrant` on `http://localhost:6333`
- `searxng` on `http://localhost:8080`

### 3. Configure environment

Edit `.env` and set at least:

- `OPENROUTER_API_KEY`
- `GENERATION_MODEL`
- `EMBEDDING_MODEL`

Optional:

- `LOCAL=true` with `LOCAL_BASE_URL` for a local OpenAI-compatible server.
- `SEARXNG_ENGINES` (default is `bing` for more stable local testing).
- `SCRAPE_PLAYWRIGHT=true` to enable JS-rendered page fallback.

### 4. Health check

```powershell
python src/cli.py doctor
```

## Run the App

### Streamlit UI

```powershell
python -m streamlit run src/app.py --server.port=8502
```

Open `http://localhost:8502`.

### CLI

Create a workbase:

```powershell
python src/cli.py create "Machine Learning Article" -d "Research project"
```

Ask a question:

```powershell
python src/cli.py ask machine-learning "Define machine learning"
```

Continue in the same workbase:

```powershell
python src/cli.py ask machine-learning "Machine learning vs deep learning"
```

Interactive chat:

```powershell
python src/cli.py chat machine-learning
```

Inspect datasets:

```powershell
python src/cli.py datasets machine-learning
```

## Multi-Tenancy and Data Isolation

- All vectors are stored in Qdrant collection: `workbase_chunks`.
- Every vector includes `workbase_id` in payload.
- Every retrieval query enforces a filter on active `workbase_id`.

This prevents data from Workbase A from appearing in Workbase B queries.

## Dataset Tracking

Each ingestion creates a new dataset ID:

- `dataset-000001`
- `dataset-000002`
- ...

Stored in:

`data/workspaces/<workbase_id>/metadata.json`

Each dataset record includes:

- query used
- source URLs
- scrape status and scrape errors
- chunk count added

## Known Operational Notes

- Search quality depends on SearxNG engine availability/rate limits.
- If embedding vector dimensions change across runs, the system validates Qdrant collection dimension and raises or recreates when safe.
- Reranker model downloads may occur on first run.

## Documentation

- CLI guide: `docs/cli.md`
- Vector schema: `docs/vector_schema.md`
- Milestones/roadmap: `docs/milestones.md`

## Contributing

Contributions are welcome. Suggested workflow:

1. Open an issue describing the bug or feature.
2. Submit a focused PR with clear reproduction/testing notes.
3. Keep changes scoped and include docs updates for behavior changes.

## Security

- Do not commit real API keys in `.env`.
- Rotate keys immediately if exposed.
- Review any remotely loaded model code when using `trust_remote_code=True`.

## License

Add your preferred OSS license (for example `MIT`) in a `LICENSE` file.
