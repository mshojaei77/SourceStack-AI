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
