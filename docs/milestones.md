# Implementation Milestones

## Milestone 1: Core Ingestion Pipeline and Qdrant Setup

Status: implemented.

- Qdrant service added to Docker Compose.
- One production collection: `workbase_chunks`.
- Mandatory `workbase_id` filter for all retrieval and count operations.
- Incremental `dataset_id` tracking per Workbase.
- Scrape status and errors recorded per source.
- Upserts are append-only at the Workbase dataset level.

Testable target:

1. Start Qdrant and SearxNG with `docker compose up -d`.
2. Create a Workbase in the UI.
3. Ask a first question.
4. Confirm `metadata.json` contains `dataset-000001`.
5. Ask a second question.
6. Confirm `metadata.json` contains `dataset-000002` and Qdrant count increases for that Workbase.

## Milestone 2: LangGraph Agent Logic and Search Integration

Status: implemented as first pass.

- LangGraph controls the pipeline nodes:
  - `plan_search`
  - `search_web`
  - `ingest_dataset`
  - `retrieve_workbase`
- Native tool calling is used to force the LLM to produce the web search query.

## Milestone 3: Reranker and UI Integration

Status: implemented as first pass.

- Initial retrieval pulls a larger candidate set.
- Reranker selects final context.
- UI shows retrieved sources with scores and dataset IDs.

## Milestone 4: Hardening

Status: next.

- Add integration tests with mocked SearxNG, Qdrant, and embeddings.
- Add Playwright browser install instructions.
- Add admin/debug page for Workbase dataset inspection.

## Phase 1 Addendum: Manual Ingestion Core

Status: implemented as first pass.

- CLI and Streamlit manual ingestion for Markdown, text, PDF, and direct URLs.
- Marker is attempted for PDFs when installed; PyMuPDF is the fallback parser.
- Manual chunks include curated trust metadata and deterministic document/chunk IDs.
- Duplicate re-ingestion skips unchanged chunks.
- Re-ingesting changed sources replaces prior chunks for the same document ID.

## Phase 2 Addendum: Technical and Retrieval Modes

Status: implemented as first pass.

- Technical domain whitelist is configurable through `.env`.
- Technical Mode adds site restrictors and applies application-level domain filtering.
- Retrieval modes are available in CLI and Streamlit.

## Phase 3 Addendum: Trust-Aware Reranking

Status: implemented as first pass.

- Reranker output includes `score_reranker`, `authority_boost`, and `score_final`.
- Curated sources receive the highest authority boost.

## Phase 4 Addendum: Model Routing

Status: partial.

- Configurable model profiles were added for planner, metadata, final answer, and deep reasoning.
- Status output reports routed planner/final/embedding/reranker models.
- Full token and dollar-cost accounting remains to be implemented.
