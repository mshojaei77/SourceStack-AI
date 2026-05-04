# CLI Usage

The CLI uses the same backend as the Streamlit UI, so it is the fastest way to test the full RAG loop.

## Check Services

```powershell
python src/cli.py doctor
```

This checks Qdrant and SearxNG.

For local testing, `.env` defaults `SEARXNG_ENGINES=bing` because some public engines may rate-limit self-hosted SearxNG instances.

## Create a Workbase

```powershell
python src/cli.py create "Machine Learning Article" -d "Research for an ML article"
```

The command prints the new Workbase ID.

## Ask One Question

```powershell
python src/cli.py ask machine-learning "Define ML"
```

The Workbase argument can be a full ID, ID prefix, exact name, or unique partial name.

Use Technical Mode and retrieval controls:

```powershell
python src/cli.py ask machine-learning "Explain autograd" --technical-mode --retrieval-mode curated_trusted
python src/cli.py ask machine-learning "Summarize my curated notes" --retrieval-mode curated_only
```

## Continue the Same Workbase

```powershell
python src/cli.py ask machine-learning "Machine Learning vs Deep Learning"
```

This creates the next dataset and retrieves from the whole Workbase history.

## Interactive Chat

```powershell
python src/cli.py chat machine-learning
```

Inside chat:

- `/info` prints Workbase metadata.
- `/datasets` prints ingestion history.
- `/exit` quits.

## Inspect Dataset History

```powershell
python src/cli.py datasets machine-learning
python src/cli.py datasets machine-learning --json
```

## Delete a Workbase

```powershell
python src/cli.py delete machine-learning --yes
```

Deletion removes the local metadata and the Qdrant points for that Workbase.

## Manual Ingestion

Ingest a trusted Markdown, text, or PDF file:

```powershell
python src/cli.py ingest-file machine-learning .\notes\chapter-1.md --title "Chapter 1 Notes"
```

Ingest a curated URL directly without using the search agent:

```powershell
python src/cli.py ingest-url machine-learning https://pytorch.org/docs/stable/autograd.html --title "PyTorch Autograd"
```

Manual ingestion creates `manual_ingestion` datasets with `trust_level=curated` and deterministic Qdrant point IDs. Re-ingesting the same source skips unchanged chunks.
