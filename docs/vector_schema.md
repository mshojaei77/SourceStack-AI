# Vector Schema

The production vector database is Qdrant.

## Collection

- Name: `workbase_chunks`
- Distance: cosine
- Vector size: created dynamically from the first successful embedding response

## Multi-Tenancy Rule

Every point must include `workbase_id`.
Every retrieval query must include this Qdrant filter:

```json
{
  "must": [
    {
      "key": "workbase_id",
      "match": { "value": "<active_workbase_id>" }
    }
  ]
}
```

This is the hard isolation boundary. No query is allowed to run without the active Workbase filter.

## Payload Fields

Each vector point stores:

| Field | Purpose |
| --- | --- |
| `workbase_id` | Strict tenant/workspace isolation key |
| `dataset_id` | Incremental ingestion identifier, e.g. `dataset-000001` |
| `source_id` | Stable source identifier for one SearxNG result |
| `title` | Source title from SearxNG |
| `url` | Scraped source URL |
| `search_query` | LLM-generated search query used for this dataset |
| `source_position` | Original SearxNG result rank |
| `chunk_index` | Chunk number within the source |
| `created_at` | UTC ingestion timestamp |
| `text` | Chunk text used for final RAG context |
| `source_origin` | `manual_curation` or `agent_web` |
| `trust_level` | `curated`, `trusted_domain`, or `general_web` |
| `is_verified` | Whether the source is treated as verified |
| `ingestion_method` | `file_upload`, `direct_url`, or `search_web` |
| `parser_name` | Parser that produced the chunk |
| `document_id` | Stable document identifier |
| `source_fingerprint` | File/content fingerprint for duplicate handling |
| `content_hash` | Chunk content hash |
| `canonical_url` | Normalized URL without tracking parameters |
| `file_name` | Uploaded file name, if any |
| `file_type` | Source file type |
| `embedding_model` | Embedding model used |
| `embedding_dim` | Vector dimension |
| `section_h1` | Nearest H1 heading context |
| `section_h2` | Nearest H2 heading context |
| `section_h3` | Nearest H3 heading context |

## Workbase Metadata

Each Workbase has a local metadata file:

```text
data/workspaces/<workbase_id>/metadata.json
```

The `datasets` array tracks every ingestion iteration:

```json
{
  "dataset_id": "dataset-000002",
  "query": "machine learning versus deep learning",
  "created_at": "2026-05-04T...",
  "chunks_added": 21,
  "sources": [
    {
      "source_id": "8bb4f2a1d98c22b0",
      "title": "Machine Learning vs Deep Learning",
      "url": "https://example.com/article",
      "position": 1,
      "scrape_status": "success",
      "scrape_error": "",
      "content_source": "trafilatura"
    }
  ]
}
```

Failed full-page scrapes are still recorded with `scrape_status = "failed"` and fall back to the SearxNG snippet when possible.

## Retrieval Modes

- `all`: all chunks in the active Workbase.
- `curated_trusted`: chunks where `trust_level` is `curated` or `trusted_domain`.
- `curated_only`: chunks where `source_origin` is `manual_curation`.

All modes still enforce the active `workbase_id` filter.
