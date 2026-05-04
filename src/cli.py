import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_assistant.config import settings
from research_assistant.citations import build_export_markdown, check_citations
from research_assistant.exporting import markdown_to_pdf, pandoc_available
from research_assistant.manual_ingest import ingest_file, ingest_url
from research_assistant.rag_pipeline import answer_message
from research_assistant.vector_store import delete_source_document, source_documents, update_document_metadata
from research_assistant.writing import build_glossary, build_outline, generate_article, generate_chapter
from research_assistant.workbases import (
    create_workbase,
    delete_workbase,
    get_workbase,
    list_workbases,
)

ANSWER_STYLES = ["Simple", "Technical", "Study Notes", "Article Draft", "Book Chapter Draft"]
RETRIEVAL_MODES = ["all", "curated_trusted", "curated_only"]


def _print_error(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return 1


def _resolve_workbase(value: str) -> dict[str, Any] | None:
    direct = get_workbase(value)
    if direct:
        return direct

    value_lower = value.lower()
    matches = [
        workbase
        for workbase in list_workbases()
        if workbase["name"].lower() == value_lower
        or workbase["id"].lower().startswith(value_lower)
        or value_lower in workbase["name"].lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(f"{item['name']} ({item['id']})" for item in matches[:8])
        raise ValueError(f"Workbase reference is ambiguous. Matches: {names}")
    return None


def _format_workbase(workbase: dict[str, Any]) -> str:
    return (
        f"{workbase['id']}\n"
        f"  name: {workbase['name']}\n"
        f"  chunks: {workbase.get('chunk_count', 0)}\n"
        f"  datasets: {len(workbase.get('datasets', []))}\n"
        f"  messages: {len(workbase.get('messages', []))}"
    )


def _parse_tags(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _citation_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {
        "author": getattr(args, "author", "") or "",
        "year": getattr(args, "year", "") or "",
        "accessed_date": getattr(args, "accessed_date", "") or "",
        "citation_key": getattr(args, "citation_key", "") or "",
    }


def _latest_assistant_message(workbase: dict[str, Any]) -> dict[str, Any] | None:
    for message in reversed(workbase.get("messages", [])):
        if message.get("role") == "assistant":
            return message
    return None


def _resolve_source(workbase_id: str, value: str) -> dict[str, Any] | None:
    value_lower = value.lower()
    sources = source_documents(workbase_id)
    matches = [
        source
        for source in sources
        if source.get("document_id") == value
        or source.get("document_id", "").lower().startswith(value_lower)
        or value_lower in (source.get("title") or "").lower()
        or value_lower in (source.get("url") or "").lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(f"{item.get('title')} ({item.get('document_id')})" for item in matches[:8])
        raise ValueError(f"Source reference is ambiguous. Matches: {names}")
    return None


def cmd_create(args: argparse.Namespace) -> int:
    result = create_workbase(args.name, args.description or "")
    if not result.ok:
        return _print_error(result.error or "Could not create workbase.")
    print(_format_workbase(result.workbase))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    workbases = list_workbases()
    if args.json:
        print(json.dumps(workbases, ensure_ascii=False, indent=2))
        return 0
    if not workbases:
        print("No workbases found.")
        return 0
    for workbase in workbases:
        print(_format_workbase(workbase))
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")

    if args.json:
        print(json.dumps(workbase, ensure_ascii=False, indent=2))
    else:
        print(_format_workbase(workbase))
        if workbase.get("description"):
            print(f"  description: {workbase['description']}")
        if workbase.get("datasets"):
            latest = workbase["datasets"][-1]
            print(f"  latest dataset: {latest.get('dataset_id')} ({latest.get('chunks_added', 0)} chunks)")
    return 0


def cmd_datasets(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")

    datasets = workbase.get("datasets", [])
    if args.json:
        print(json.dumps(datasets, ensure_ascii=False, indent=2))
        return 0
    if not datasets:
        print("No datasets ingested yet.")
        return 0

    for dataset in datasets:
        failed = sum(1 for source in dataset.get("sources", []) if source.get("scrape_status") == "failed")
        print(
            f"{dataset.get('dataset_id')} | chunks={dataset.get('chunks_added', 0)} | "
            f"sources={len(dataset.get('sources', []))} | failed_scrapes={failed}"
        )
        print(f"  query: {dataset.get('query', '')}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")

    if not args.yes:
        typed = input(f"Delete '{workbase['name']}' and its Qdrant points? Type the workbase id to confirm: ")
        if typed.strip() != workbase["id"]:
            print("Delete cancelled.")
            return 0

    delete_workbase(workbase["id"])
    print(f"Deleted {workbase['name']} ({workbase['id']}).")
    return 0


def _run_question(
    workbase_id: str,
    question: str,
    model: str | None,
    show_status: bool,
    technical_mode: bool | None = None,
    retrieval_mode: str = "all",
    answer_style: str = "Simple",
    document_id: str | None = None,
    tags: list[str] | None = None,
) -> tuple[str, list[dict]]:
    answer = ""
    sources: list[dict] = []
    for event in answer_message(
        workbase_id,
        question,
        model=model,
        technical_mode=technical_mode,
        retrieval_mode=retrieval_mode,
        answer_style=answer_style,
        document_id=document_id,
        tags=tags,
    ):
        if event["type"] == "status":
            if show_status:
                print(f"[status] {event['content']}", file=sys.stderr)
        elif event["type"] == "token":
            answer += event["content"]
            print(event["content"], end="", flush=True)
        elif event["type"] == "sources":
            sources = event["content"]
    print()
    return answer, sources


def _print_sources(sources: list[dict]) -> None:
    if not sources:
        return
    print("\nSources:")
    for index, source in enumerate(sources, start=1):
        print(
            f"[{index}] {source.get('title', 'Untitled')} | "
            f"{source.get('dataset_id', 'unknown dataset')} | "
            f"{source.get('trust_level', 'general_web')} | "
            f"score={source.get('score_final', source.get('score', 0.0)):.3f}"
        )
        if source.get("url"):
            print(f"    {source['url']}")


def cmd_ask(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")

    technical_mode = True if args.technical_mode else None
    document_id = args.document_id
    if args.source:
        try:
            source = _resolve_source(workbase["id"], args.source)
        except ValueError as exc:
            return _print_error(str(exc))
        if not source:
            return _print_error("Source not found.")
        document_id = source["document_id"]
    answer, sources = _run_question(
        workbase["id"],
        args.question,
        args.model,
        not args.no_status,
        technical_mode=technical_mode,
        retrieval_mode=args.retrieval_mode,
        answer_style=args.answer_style,
        document_id=document_id,
        tags=_parse_tags(args.tags),
    )
    if args.json:
        print(json.dumps({"answer": answer, "sources": sources}, ensure_ascii=False, indent=2))
    elif not args.no_sources:
        _print_sources(sources)
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")

    print(f"Chatting in {workbase['name']} ({workbase['id']}).")
    print("Type /exit to quit, /datasets to inspect ingestions, /info for workbase metadata.")
    while True:
        try:
            question = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not question:
            continue
        if question in {"/exit", "/quit"}:
            return 0
        if question == "/info":
            fresh = get_workbase(workbase["id"]) or workbase
            print(_format_workbase(fresh))
            continue
        if question == "/datasets":
            fresh = get_workbase(workbase["id"]) or workbase
            for dataset in fresh.get("datasets", []):
                print(f"{dataset.get('dataset_id')} | {dataset.get('query')} | chunks={dataset.get('chunks_added', 0)}")
            continue

        print("Assistant> ", end="", flush=True)
        _, sources = _run_question(
            workbase["id"],
            question,
            args.model,
            not args.no_status,
            technical_mode=True if args.technical_mode else None,
            retrieval_mode=args.retrieval_mode,
            answer_style=args.answer_style,
            tags=_parse_tags(args.tags),
        )
        if not args.no_sources:
            _print_sources(sources)


def cmd_doctor(args: argparse.Namespace) -> int:
    ok = True
    print("Configuration:")
    print(f"  SearxNG: {settings.searxng_url}")
    print(f"  Qdrant: {settings.qdrant_url}")
    print(f"  Collection: {settings.qdrant_collection}")
    print(f"  Workspaces: {settings.resolved_workbases_dir}")

    try:
        import requests

        response = requests.get(f"{settings.qdrant_url.rstrip('/')}/collections", timeout=5)
        print(f"Qdrant: {response.status_code}")
        ok = ok and response.ok
    except Exception as exc:
        print(f"Qdrant: failed ({exc})")
        ok = False

    try:
        import requests

        response = requests.get(
            f"{settings.searxng_url.rstrip('/')}/search",
            params={"q": args.query, "format": "json", "engines": settings.searxng_engines},
            timeout=15,
        )
        print(f"SearxNG: {response.status_code}")
        if response.ok:
            data = response.json()
            print(f"SearxNG results: {len(data.get('results', []))}")
        ok = ok and response.ok
    except Exception as exc:
        print(f"SearxNG: failed ({exc})")
        ok = False

    return 0 if ok else 1


def cmd_ingest_file(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")
    result = ingest_file(
        workbase["id"],
        args.path,
        title=args.title or "",
        notes=args.notes or "",
        tags=_parse_tags(args.tags),
        citation=_citation_from_args(args),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else _format_ingest_result(result))
    return 0


def cmd_ingest_url(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")
    result = ingest_url(
        workbase["id"],
        args.url,
        title=args.title or "",
        notes=args.notes or "",
        tags=_parse_tags(args.tags),
        citation=_citation_from_args(args),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else _format_ingest_result(result))
    return 0


def _format_ingest_result(result: dict[str, Any]) -> str:
    return (
        f"Source added: {result.get('title', '')}\n"
        f"  dataset: {result.get('dataset_id', '')}\n"
        f"  document: {result.get('document_id', '')}\n"
        f"  parser: {result.get('parser_name', '')}\n"
        f"  chunks added: {result.get('chunks_added', 0)}\n"
        f"  chunks updated: {result.get('chunks_updated', 0)}\n"
        f"  duplicates skipped: {result.get('duplicates_skipped', 0)}\n"
        f"  total chunks: {result.get('total_chunks', 0)}"
    )


def cmd_sources(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")

    sources = source_documents(workbase["id"])
    if args.json:
        print(json.dumps(sources, ensure_ascii=False, indent=2))
        return 0
    if not sources:
        print("No sources found.")
        return 0
    for source in sources:
        print(
            f"{source.get('document_id')} | {source.get('title', 'Untitled')} | "
            f"type={source.get('file_type', 'web')} | trust={source.get('trust_level', 'general_web')} | "
            f"chunks={source.get('chunk_count', 0)} | datasets={','.join(source.get('dataset_ids', []))}"
        )
        if source.get("tags"):
            print(f"  tags: {', '.join(source['tags'])}")
        if source.get("url"):
            print(f"  url: {source['url']}")
    return 0


def cmd_source_view(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
        source = _resolve_source(workbase["id"], args.source) if workbase else None
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")
    if not source:
        return _print_error("Source not found.")
    print(json.dumps(source, ensure_ascii=False, indent=2) if args.json else _format_source(source))
    return 0


def _format_source(source: dict[str, Any]) -> str:
    fields = [
        ("document", source.get("document_id", "")),
        ("title", source.get("title", "")),
        ("type", source.get("file_type", "")),
        ("trust", source.get("trust_level", "")),
        ("chunks", source.get("chunk_count", 0)),
        ("datasets", ", ".join(source.get("dataset_ids", []))),
        ("tags", ", ".join(source.get("tags", []))),
        ("author", source.get("author", "")),
        ("year", source.get("year", "")),
        ("url", source.get("url", "")),
    ]
    return "\n".join(f"{name}: {value}" for name, value in fields if value not in {"", None})


def cmd_source_update(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
        source = _resolve_source(workbase["id"], args.source) if workbase else None
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")
    if not source:
        return _print_error("Source not found.")

    updates: dict[str, Any] = {}
    for attr in ["title", "author", "year", "url", "accessed_date", "citation_key"]:
        value = getattr(args, attr)
        if value is not None:
            updates[attr] = value
    if args.url is not None:
        updates["canonical_url"] = args.url
    if args.tags is not None:
        updates["tags"] = _parse_tags(args.tags)
    if not updates:
        return _print_error("No metadata updates were provided.")
    changed = update_document_metadata(workbase["id"], source["document_id"], updates)
    print(f"Updated {changed} chunks for {source['document_id']}.")
    return 0


def cmd_source_delete(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
        source = _resolve_source(workbase["id"], args.source) if workbase else None
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")
    if not source:
        return _print_error("Source not found.")
    removed = delete_source_document(workbase["id"], source["document_id"])
    print(f"Deleted {removed} chunks from {source.get('title', source['document_id'])}.")
    return 0


def cmd_source_reingest(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
        source = _resolve_source(workbase["id"], args.source) if workbase else None
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")
    if not source:
        return _print_error("Source not found.")

    citation = {
        "author": source.get("author", ""),
        "year": source.get("year", ""),
        "accessed_date": source.get("accessed_date", ""),
        "citation_key": source.get("citation_key", ""),
    }
    if source.get("stored_file_path") and Path(source["stored_file_path"]).exists():
        result = ingest_file(
            workbase["id"],
            source["stored_file_path"],
            title=source.get("title", ""),
            source_name=source.get("file_name") or Path(source["stored_file_path"]).name,
            tags=source.get("tags", []),
            citation=citation,
        )
    elif source.get("url"):
        result = ingest_url(
            workbase["id"],
            source["url"],
            title=source.get("title", ""),
            tags=source.get("tags", []),
            citation=citation,
        )
    else:
        return _print_error("Source cannot be re-ingested because no stored file path or URL is available.")
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else _format_ingest_result(result))
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")

    if args.kind == "article":
        result = generate_article(
            workbase["id"],
            args.topic,
            args.audience,
            args.tone,
            args.length,
            args.required_sources or "",
            args.retrieval_mode,
            model=args.model,
        )
        title = args.topic or "Article Draft"
    elif args.kind == "chapter":
        result = generate_chapter(
            workbase["id"],
            args.chapter_title or args.topic,
            args.goal or "",
            args.reader_level,
            args.length,
            args.style_notes or "",
            args.required_sources or "",
            args.retrieval_mode,
            model=args.model,
        )
        title = args.chapter_title or args.topic or "Book Chapter Draft"
    elif args.kind == "outline":
        result = build_outline(workbase["id"], args.topic, args.work_type, args.retrieval_mode, model=args.model)
        title = args.topic or "Outline"
    else:
        result = build_glossary(workbase["id"], args.topic, args.retrieval_mode, model=args.model)
        title = args.topic or "Glossary"

    if args.output:
        markdown = build_export_markdown(title, result["content"], result.get("sources", []), workbase["name"])
        Path(args.output).write_text(markdown, encoding="utf-8")
        print(f"Wrote {args.output}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["content"])
        _print_sources(result.get("sources", []))
    return 0


def cmd_citations_check(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase) if args.workbase else None
    except ValueError as exc:
        return _print_error(str(exc))
    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
        sources = json.loads(Path(args.sources_json).read_text(encoding="utf-8")) if args.sources_json else []
    else:
        if not workbase:
            return _print_error("Workbase is required when --file is not used.")
        message = _latest_assistant_message(workbase)
        if not message:
            return _print_error("No assistant message found to check.")
        content = message.get("content", "")
        sources = message.get("sources", [])
    issues = check_citations(content, sources, args.retrieval_mode)
    print(json.dumps(issues, ensure_ascii=False, indent=2) if args.json else "\n".join(f"- {issue}" for issue in issues))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    try:
        workbase = _resolve_workbase(args.workbase)
    except ValueError as exc:
        return _print_error(str(exc))
    if not workbase:
        return _print_error("Workbase not found.")

    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
        sources = json.loads(Path(args.sources_json).read_text(encoding="utf-8")) if args.sources_json else []
    else:
        message = _latest_assistant_message(workbase)
        if not message:
            return _print_error("No assistant message found to export.")
        content = message.get("content", "")
        sources = message.get("sources", [])

    markdown = build_export_markdown(args.title or workbase["name"], content, sources, workbase["name"])
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
        print(f"Wrote Markdown: {args.output}")
    else:
        print(markdown)

    if args.pdf:
        pdf_bytes, error = markdown_to_pdf(markdown, args.title or workbase["name"])
        if pdf_bytes:
            pdf_path = args.pdf_output or str(Path(args.output or "sourcestack-export.md").with_suffix(".pdf"))
            Path(pdf_path).write_bytes(pdf_bytes)
            print(f"Wrote PDF: {pdf_path}")
        else:
            print(error, file=sys.stderr)
    return 0


def cmd_self_test(args: argparse.Namespace) -> int:
    from research_assistant import rag_pipeline as rag_mod
    from research_assistant import vector_store as vector_mod
    from research_assistant import writing as writing_mod
    from research_assistant import manual_ingest as ingest_mod
    from research_assistant.citations import ensure_references
    from research_assistant.search import is_whitelisted_domain, technical_query

    original_embed = vector_mod.embed
    original_chat = writing_mod.chat
    original_stream = rag_mod.stream_chat
    original_rerank = rag_mod.rerank
    original_parse_url = ingest_mod.parse_url

    try:
        collection = vector_mod.client().get_collection(settings.qdrant_collection)
        vectors = collection.config.params.vectors
        vector_size = int(getattr(vectors, "size", 8) or 8)
    except Exception:
        vector_size = 8

    def fake_embed(text: str) -> list[float]:
        base = float((sum(ord(ch) for ch in text) % 97) + 1)
        seed = [base / 100.0, len(text) / 1000.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        return [seed[index % len(seed)] for index in range(vector_size)]

    def fake_chat(messages: list[dict[str, Any]], model: str | None = None, tools: list[dict] | None = None, task: str = "final") -> dict:
        return {
            "content": "Generated test content grounded in the supplied source. [1]",
            "model": f"fake-{task}",
            "usage": {"input_tokens": 10, "output_tokens": 8, "total_tokens": 18},
            "tool_calls": [],
        }

    def fake_stream(messages: list[dict[str, Any]], model: str | None = None, task: str = "final"):
        yield "Self-test answer using the selected source style. [1]"

    def fake_parse_url(url: str, title: str = ""):
        return ingest_mod.ParsedSource(
            title=title or "Fake URL Source",
            text="# Fake URL\n\nTrusted web content about SourceStack citations.",
            parser_name="self_test",
            parser_version="1",
            file_type="url",
            canonical_url=url,
        )

    vector_mod.embed = fake_embed
    writing_mod.chat = fake_chat
    rag_mod.stream_chat = fake_stream
    rag_mod.rerank = lambda query, rows, top_k: rows[:top_k]
    ingest_mod.parse_url = fake_parse_url

    checks: list[str] = []
    workbase_id = ""
    try:
        result = create_workbase("SourceStack CLI Self Test", "Temporary CLI feature test")
        if not result.ok or not result.workbase:
            return _print_error(result.error or "Could not create self-test workbase.")
        workbase_id = result.workbase["id"]
        checks.append("create workbase")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            md_path = temp / "chapter.md"
            md_path.write_text("# Chapter 1\n\n## RAG\n\nRetrieval keeps answers grounded.\n\n```python\nprint('keep indentation')\n```", encoding="utf-8")
            txt_path = temp / "notes.txt"
            txt_path.write_text("Plain text source about citations and exports.", encoding="utf-8")
            pdf_path = temp / "paper.pdf"
            try:
                import fitz

                pdf = fitz.open()
                page = pdf.new_page()
                page.insert_text((72, 72), "PDF source for SourceStack AI self test.")
                pdf.save(pdf_path)
                pdf.close()
            except Exception:
                pdf_path.write_bytes(b"%PDF-1.4\n% self-test placeholder\n")

            md_result = ingest_file(workbase_id, md_path, title="Markdown Chapter", tags=["RAG", "Chapter 1"], citation={"author": "Tester", "year": "2026"})
            duplicate_result = ingest_file(workbase_id, md_path, title="Markdown Chapter", tags=["RAG", "Chapter 1"])
            txt_result = ingest_file(workbase_id, txt_path, title="Text Notes", tags=["Notes"])
            pdf_result = ingest_file(workbase_id, pdf_path, title="PDF Paper", tags=["Research Paper"])
            url_result = ingest_url(workbase_id, "https://example.com/source", title="Curated URL", tags=["Official Docs"])
            checks.append("manual ingest markdown/text/pdf/url")
            if duplicate_result["duplicates_skipped"] < 1:
                return _print_error("Duplicate ingestion did not skip existing chunks.")
            checks.append("duplicate handling")

            sources = source_documents(workbase_id)
            if len(sources) < 4:
                return _print_error(f"Expected at least 4 sources, found {len(sources)}.")
            checks.append("source library")

            first = sources[0]
            update_document_metadata(workbase_id, first["document_id"], {"tags": ["Updated"], "author": "CLI Tester"})
            checks.append("metadata edit and tags")

            answer = ""
            answer_sources: list[dict] = []
            for style in ANSWER_STYLES:
                for event in answer_message(workbase_id, "What is SourceStack testing?", retrieval_mode="curated_only", answer_style=style):
                    if event["type"] == "token":
                        answer += event["content"]
                    elif event["type"] == "sources":
                        answer_sources = event["content"]
            checks.append("answer styles and curated retrieval")

            source_answer = ""
            for event in answer_message(
                workbase_id,
                "Ask only this source",
                retrieval_mode="curated_only",
                document_id=first["document_id"],
            ):
                if event["type"] == "token":
                    source_answer += event["content"]
            if "[1]" not in source_answer:
                return _print_error("Ask-this-source answer did not include a citation.")
            checks.append("ask this source")

            article = generate_article(workbase_id, "RAG citations", "students", "clear", "short", retrieval_mode="curated_only")
            chapter = generate_chapter(workbase_id, "RAG Chapter", "teach citations", "beginner", "short", retrieval_mode="curated_only")
            outline = build_outline(workbase_id, "RAG citations", "article", retrieval_mode="curated_only")
            glossary = build_glossary(workbase_id, "RAG citations", retrieval_mode="curated_only")
            if not all(item["sources"] for item in [article, chapter, outline, glossary]):
                return _print_error("Writing tools did not attach sources.")
            checks.append("writing tools")

            cited = ensure_references("A grounded sentence. [1]", answer_sources or article["sources"])
            issues = check_citations(cited, answer_sources or article["sources"], "curated_only")
            if not issues:
                return _print_error("Citation checker returned no result.")
            checks.append("citations and references")

            export_md = build_export_markdown("Self Test Export", article["content"], article["sources"], result.workbase["name"])
            if "## References" not in export_md or "## Source List" not in export_md:
                return _print_error("Markdown export is missing references or source list.")
            _, pdf_error = markdown_to_pdf(export_md, "Self Test Export")
            if not pandoc_available() and "Pandoc" not in pdf_error:
                return _print_error("PDF export did not report missing Pandoc clearly.")
            checks.append("markdown/pdf export")

            if not is_whitelisted_domain("https://docs.python.org/3/") or "site:" not in technical_query("typing docs"):
                return _print_error("Technical mode whitelist helpers failed.")
            checks.append("technical mode filtering")

            removed = delete_source_document(workbase_id, first["document_id"])
            if removed < 1:
                return _print_error("Source delete removed no chunks.")
            checks.append("delete source")

        if args.json:
            print(json.dumps({"ok": True, "checks": checks, "workbase_id": workbase_id}, ensure_ascii=False, indent=2))
        else:
            print("Self-test passed:")
            for check in checks:
                print(f"- {check}")
        return 0
    finally:
        vector_mod.embed = original_embed
        writing_mod.chat = original_chat
        rag_mod.stream_chat = original_stream
        rag_mod.rerank = original_rerank
        ingest_mod.parse_url = original_parse_url
        if workbase_id and not args.keep_workbase:
            delete_workbase(workbase_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI for the Research Assistant RAG platform.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a workbase.")
    create.add_argument("name")
    create.add_argument("-d", "--description", default="")
    create.set_defaults(func=cmd_create)

    list_cmd = subparsers.add_parser("list", help="List workbases.")
    list_cmd.add_argument("--json", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    info = subparsers.add_parser("info", help="Show workbase metadata.")
    info.add_argument("workbase")
    info.add_argument("--json", action="store_true")
    info.set_defaults(func=cmd_info)

    datasets = subparsers.add_parser("datasets", help="Show dataset ingestion history.")
    datasets.add_argument("workbase")
    datasets.add_argument("--json", action="store_true")
    datasets.set_defaults(func=cmd_datasets)

    delete = subparsers.add_parser("delete", help="Delete a workbase and its vector points.")
    delete.add_argument("workbase")
    delete.add_argument("-y", "--yes", action="store_true")
    delete.set_defaults(func=cmd_delete)

    ask = subparsers.add_parser("ask", help="Ask a single question in a workbase.")
    ask.add_argument("workbase")
    ask.add_argument("question")
    ask.add_argument("--model")
    ask.add_argument("--json", action="store_true")
    ask.add_argument("--no-status", action="store_true")
    ask.add_argument("--no-sources", action="store_true")
    ask.add_argument("--technical-mode", action="store_true")
    ask.add_argument("--answer-style", choices=ANSWER_STYLES, default="Simple")
    ask.add_argument("--document-id", help="Restrict retrieval to a single document id.")
    ask.add_argument("--source", help="Restrict retrieval to one source by title, URL, or document id prefix.")
    ask.add_argument("--tags", default="", help="Comma-separated source tags to filter retrieval.")
    ask.add_argument(
        "--retrieval-mode",
        choices=RETRIEVAL_MODES,
        default="all",
    )
    ask.set_defaults(func=cmd_ask)

    chat = subparsers.add_parser("chat", help="Start an interactive chat in a workbase.")
    chat.add_argument("workbase")
    chat.add_argument("--model")
    chat.add_argument("--no-status", action="store_true")
    chat.add_argument("--no-sources", action="store_true")
    chat.add_argument("--technical-mode", action="store_true")
    chat.add_argument("--answer-style", choices=ANSWER_STYLES, default="Simple")
    chat.add_argument("--tags", default="", help="Comma-separated source tags to filter retrieval.")
    chat.add_argument(
        "--retrieval-mode",
        choices=RETRIEVAL_MODES,
        default="all",
    )
    chat.set_defaults(func=cmd_chat)

    doctor = subparsers.add_parser("doctor", help="Check local services and configuration.")
    doctor.add_argument("--query", default="machine learning definition")
    doctor.set_defaults(func=cmd_doctor)

    ingest_file_cmd = subparsers.add_parser("ingest-file", help="Manually ingest a PDF, Markdown, or text file.")
    ingest_file_cmd.add_argument("workbase")
    ingest_file_cmd.add_argument("path")
    ingest_file_cmd.add_argument("--title", default="")
    ingest_file_cmd.add_argument("--notes", default="")
    ingest_file_cmd.add_argument("--tags", default="")
    ingest_file_cmd.add_argument("--author", default="")
    ingest_file_cmd.add_argument("--year", default="")
    ingest_file_cmd.add_argument("--accessed-date", default="")
    ingest_file_cmd.add_argument("--citation-key", default="")
    ingest_file_cmd.add_argument("--json", action="store_true")
    ingest_file_cmd.set_defaults(func=cmd_ingest_file)

    ingest_url_cmd = subparsers.add_parser("ingest-url", help="Manually ingest a curated URL.")
    ingest_url_cmd.add_argument("workbase")
    ingest_url_cmd.add_argument("url")
    ingest_url_cmd.add_argument("--title", default="")
    ingest_url_cmd.add_argument("--notes", default="")
    ingest_url_cmd.add_argument("--tags", default="")
    ingest_url_cmd.add_argument("--author", default="")
    ingest_url_cmd.add_argument("--year", default="")
    ingest_url_cmd.add_argument("--accessed-date", default="")
    ingest_url_cmd.add_argument("--citation-key", default="")
    ingest_url_cmd.add_argument("--json", action="store_true")
    ingest_url_cmd.set_defaults(func=cmd_ingest_url)

    sources = subparsers.add_parser("sources", help="List sources in a workbase.")
    sources.add_argument("workbase")
    sources.add_argument("--json", action="store_true")
    sources.set_defaults(func=cmd_sources)

    source_view = subparsers.add_parser("source-view", help="Show source metadata.")
    source_view.add_argument("workbase")
    source_view.add_argument("source")
    source_view.add_argument("--json", action="store_true")
    source_view.set_defaults(func=cmd_source_view)

    source_update = subparsers.add_parser("source-update", help="Edit source citation metadata and tags.")
    source_update.add_argument("workbase")
    source_update.add_argument("source")
    source_update.add_argument("--title")
    source_update.add_argument("--author")
    source_update.add_argument("--year")
    source_update.add_argument("--url")
    source_update.add_argument("--accessed-date")
    source_update.add_argument("--citation-key")
    source_update.add_argument("--tags")
    source_update.set_defaults(func=cmd_source_update)

    source_delete = subparsers.add_parser("source-delete", help="Delete one source and its chunks.")
    source_delete.add_argument("workbase")
    source_delete.add_argument("source")
    source_delete.set_defaults(func=cmd_source_delete)

    source_reingest = subparsers.add_parser("source-reingest", help="Re-ingest one source from its stored file or URL.")
    source_reingest.add_argument("workbase")
    source_reingest.add_argument("source")
    source_reingest.add_argument("--json", action="store_true")
    source_reingest.set_defaults(func=cmd_source_reingest)

    write = subparsers.add_parser("write", help="Generate article, chapter, outline, or glossary from a workbase.")
    write.add_argument("workbase")
    write.add_argument("kind", choices=["article", "chapter", "outline", "glossary"])
    write.add_argument("--topic", default="")
    write.add_argument("--audience", default="Beginners")
    write.add_argument("--tone", default="Clear and practical")
    write.add_argument("--length", default="short")
    write.add_argument("--required-sources", default="")
    write.add_argument("--chapter-title", default="")
    write.add_argument("--goal", default="")
    write.add_argument("--reader-level", default="Beginner")
    write.add_argument("--style-notes", default="")
    write.add_argument("--work-type", choices=["article", "book chapter"], default="article")
    write.add_argument("--retrieval-mode", choices=RETRIEVAL_MODES, default="all")
    write.add_argument("--model")
    write.add_argument("--output")
    write.add_argument("--json", action="store_true")
    write.set_defaults(func=cmd_write)

    citations_check = subparsers.add_parser("citations-check", help="Run basic citation hygiene checks.")
    citations_check.add_argument("workbase", nargs="?")
    citations_check.add_argument("--file")
    citations_check.add_argument("--sources-json")
    citations_check.add_argument("--retrieval-mode", choices=RETRIEVAL_MODES, default="all")
    citations_check.add_argument("--json", action="store_true")
    citations_check.set_defaults(func=cmd_citations_check)

    export = subparsers.add_parser("export", help="Export latest answer or a Markdown file.")
    export.add_argument("workbase")
    export.add_argument("--file")
    export.add_argument("--sources-json")
    export.add_argument("--title", default="")
    export.add_argument("--output")
    export.add_argument("--pdf", action="store_true")
    export.add_argument("--pdf-output")
    export.set_defaults(func=cmd_export)

    self_test = subparsers.add_parser("self-test", help="Run deterministic CLI checks for SourceStack features.")
    self_test.add_argument("--json", action="store_true")
    self_test.add_argument("--keep-workbase", action="store_true")
    self_test.set_defaults(func=cmd_self_test)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
