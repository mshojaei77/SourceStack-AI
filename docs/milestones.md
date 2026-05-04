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
