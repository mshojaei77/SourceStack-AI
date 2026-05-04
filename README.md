# SourceStack AI

SourceStack AI is a beginner-friendly research and writing assistant.

Product promise:

```text
Upload or collect trusted sources, ask questions, generate cited writing, and export clean reports.
```

The app is intentionally simple. It is built around Workbases: isolated research spaces where sources, chunks, chat history, citations, and generated writing stay together.

## Core Flow

```text
Create Workbase
-> Add sources manually or through web search
-> Ask questions
-> Generate article/chapter/report
-> Review sources and citations
-> Export to Markdown or PDF
```

## Key Features

- Workbases with strict data isolation in Qdrant.
- Manual ingestion for PDF, Markdown, text, and curated URLs.
- Web ingestion through self-hosted SearxNG.
- Duplicate-safe document and chunk IDs.
- Source Library with metadata, tags, trust badges, delete, re-ingest, and ask-one-source controls.
- Retrieval modes: all sources, curated only, or curated + trusted web.
- Answer styles: Simple, Technical, Study Notes, Article Draft, Book Chapter Draft.
- Writing tools for articles, book chapters, outlines, and glossaries.
- Inline numbered citations and Markdown references.
- Citation hygiene checks.
- Markdown export and optional Pandoc PDF export.
- Technical Mode with an application-level trusted domain whitelist.
- Configurable model routing, budget mode, local reranker support, and embedding cache by chunk hash.

## Architecture

Core RAG flow:

1. `plan_search`: use a small/planner model to produce a focused search query.
2. `search_web`: query SearxNG, optionally with technical-domain restrictions.
3. `ingest_dataset`: scrape, chunk, embed, and upsert evidence into Qdrant.
4. `retrieve_workbase`: retrieve by Workbase, retrieval mode, source, and tags.
5. `rerank`: prefer local reranking when available.
6. `final generation`: write the answer or draft with inline citations.

Stack:

- UI: Streamlit
- CLI: `argparse`
- Vector DB: Qdrant
- Search: self-hosted SearxNG
- Scraping: Trafilatura + BeautifulSoup + optional Playwright
- PDF parsing: Marker first, PyMuPDF fallback
- Orchestration: LangGraph
- LLM and embeddings: OpenAI-compatible endpoint through OpenRouter or a local server

## Project Structure

```text
.
|- config/
|  `- searxng/
|- data/
|  `- workspaces/
|- docs/
|- src/
|  |- app.py
|  |- cli.py
|  `- research_assistant/
|     |- citations.py
|     |- config.py
|     |- exporting.py
|     |- llm.py
|     |- manual_ingest.py
|     |- rag_pipeline.py
|     |- reranker.py
|     |- search.py
|     |- text.py
|     |- vector_store.py
|     |- workbases.py
|     `- writing.py
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

- Qdrant: `http://localhost:6333`
- SearxNG: `http://localhost:8080`

### 3. Configure environment

Edit `.env` and set at least:

```env
OPENROUTER_API_KEY=...
GENERATION_MODEL=...
EMBEDDING_MODEL=...
```

Useful routing defaults:

```env
LLM_MODEL_SMALL=openai/gpt-4.1-nano
LLM_MODEL_DEFAULT=openai/gpt-4.1-mini
LLM_MODEL_STRONG=openai/gpt-4.1
EMBEDDING_MODEL=text-embedding-3-small
RERANKER_MODEL=BAAI/bge-reranker-base
BUDGET_MODE=true
```

For a local OpenAI-compatible server:

```env
LOCAL=true
LOCAL_BASE_URL=http://localhost:8000/v1
LOCAL_GENERATION_MODEL=Qwen/Qwen3-4B-Instruct-2507
LOCAL_EMBEDDING_MODEL=Octen/Octen-Embedding-8B
```

### 4. Health check

```powershell
python src/cli.py doctor
```

## Run the App

```powershell
python -m streamlit run src/app.py --server.port=8502
```

Open `http://localhost:8502`.

The Streamlit app has four main tabs:

- Ask
- Source Library
- Writing Tools
- Export & Review

## CLI Usage

Create a Workbase:

```powershell
python src/cli.py create "Machine Learning Article" -d "Research project"
```

List and inspect Workbases:

```powershell
python src/cli.py list
python src/cli.py info machine-learning
python src/cli.py datasets machine-learning
```

### Manual Ingestion

Ingest Markdown, text, or PDF:

```powershell
python src/cli.py ingest-file machine-learning .\notes\chapter-1.md --title "Chapter 1 Notes" --tags "RAG,Chapter 1" --author "A. Writer" --year 2026
```

Ingest a curated URL:

```powershell
python src/cli.py ingest-url machine-learning https://pytorch.org/docs/stable/autograd.html --title "PyTorch Autograd" --tags "Official Docs,Autograd"
```

Uploading or ingesting the same source again should skip duplicate chunks. If a web source is later manually ingested, it is upgraded to curated metadata.

### Source Library

List sources:

```powershell
python src/cli.py sources machine-learning
```

View one source:

```powershell
python src/cli.py source-view machine-learning "PyTorch Autograd"
```

Edit citation metadata and tags:

```powershell
python src/cli.py source-update machine-learning "PyTorch Autograd" --author "PyTorch Team" --year 2026 --tags "Official Docs,Autograd,Trusted"
```

Re-ingest or delete a source:

```powershell
python src/cli.py source-reingest machine-learning "PyTorch Autograd"
python src/cli.py source-delete machine-learning "PyTorch Autograd"
```

### Ask Questions

Ask using all sources:

```powershell
python src/cli.py ask machine-learning "Define retrieval augmented generation"
```

Use a specific answer style:

```powershell
python src/cli.py ask machine-learning "Explain embeddings" --answer-style "Study Notes"
```

Use curated-only retrieval:

```powershell
python src/cli.py ask machine-learning "Summarize my verified material" --retrieval-mode curated_only
```

Ask only one source:

```powershell
python src/cli.py ask machine-learning "Explain autograd from this source" --source "PyTorch Autograd" --retrieval-mode curated_only
```

Filter by tags:

```powershell
python src/cli.py ask machine-learning "What belongs in chapter 1?" --tags "Chapter 1" --retrieval-mode curated_only
```

Use Technical Mode:

```powershell
python src/cli.py ask machine-learning "Find official docs for vector search" --technical-mode --retrieval-mode curated_trusted
```

### Writing Tools

Generate an article:

```powershell
python src/cli.py write machine-learning article --topic "RAG for Beginners" --audience "Students" --tone "Clear and practical" --length "900 words" --retrieval-mode curated_trusted --output rag-article.md
```

Generate a book chapter:

```powershell
python src/cli.py write machine-learning chapter --chapter-title "Introduction to RAG" --goal "Teach the basics with citations" --reader-level "Beginner" --length "1500 words" --retrieval-mode curated_only --output chapter-1.md
```

Build an outline:

```powershell
python src/cli.py write machine-learning outline --topic "Vector Databases" --work-type article --retrieval-mode curated_trusted
```

Build a glossary:

```powershell
python src/cli.py write machine-learning glossary --topic "RAG and embeddings" --retrieval-mode curated_only
```

### Citations and Export

Check citations on the latest assistant answer:

```powershell
python src/cli.py citations-check machine-learning
```

Export the latest assistant answer to Markdown:

```powershell
python src/cli.py export machine-learning --title "Research Summary" --output research-summary.md
```

Export to PDF when Pandoc is installed:

```powershell
python src/cli.py export machine-learning --title "Research Summary" --output research-summary.md --pdf --pdf-output research-summary.pdf
```

If Pandoc is missing, PDF export prints a clear warning and Markdown export still works.

## Technical Mode

Technical Mode does two things:

1. Adds `site:` restrictions to search queries.
2. Filters returned URLs in application code.

The default whitelist is configured in `src/research_assistant/config.py` and can be overridden with:

```env
TECHNICAL_DOMAIN_WHITELIST=arxiv.org,github.com,huggingface.co,openai.com,platform.openai.com,docs.anthropic.com,anthropic.com,pytorch.org,tensorflow.org,qdrant.tech,langchain.com,python.org,learn.microsoft.com,developer.mozilla.org
```

Source trust badges:

- `Curated`: manual uploads and manually added URLs
- `Trusted Web`: web source from a whitelisted domain
- `Web`: general web source

## Cost Controls

SourceStack AI routes work by task:

- Small/planner model: search query generation, query rewriting, metadata cleanup, simple summaries.
- Default/strong model: final answers, article writing, chapter writing, technical explanation.
- Embedding model: configurable through `EMBEDDING_MODEL`.
- Reranker: local by default when practical.

Budget mode reduces work:

```env
BUDGET_MODE=true
MAX_SEARCH_RESULTS=5
MAX_SCRAPE_PAGES=5
RETRIEVAL_CANDIDATE_K=30
FINAL_CONTEXT_K=8
```

Embedding responses are cached by embedding model and chunk hash in `data/embedding_cache.json`.

Set `DEBUG_COSTS=true` to show rough model/token/cost logging in status output.

## Testing

Run syntax checks:

```powershell
python -m compileall src
```

Run deterministic CLI coverage for the new SourceStack feature surface:

```powershell
python src/cli.py self-test
```

The self-test creates a temporary Workbase and checks:

- Workbase creation
- Markdown, text, PDF, and URL ingestion
- Duplicate handling
- Source Library listing
- metadata editing and tags
- answer styles and retrieval modes
- ask-this-source
- article, chapter, outline, and glossary tools
- citations and references
- Markdown/PDF export path
- Technical Mode whitelist helpers
- source deletion

The test uses deterministic local fakes for embedding and generation so it does not spend LLM credits. Qdrant should be running.

## Operational Notes

- Search quality depends on SearxNG engine availability and rate limits.
- If embedding vector dimensions change across runs, the system validates the Qdrant collection dimension and raises or recreates only when safe.
- Reranker model downloads may occur on first real reranker use.
- PDF export requires Pandoc. Markdown export does not.
- Do not commit real API keys in `.env`.

## Documentation

- CLI guide: `docs/cli.md`
- Vector schema: `docs/vector_schema.md`
- Milestones/roadmap: `docs/milestones.md`

## License

Add your preferred OSS license, for example MIT, in a `LICENSE` file.
