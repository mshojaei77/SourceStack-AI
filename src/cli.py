import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_assistant.config import settings
from research_assistant.rag_pipeline import answer_message
from research_assistant.workbases import (
    create_workbase,
    delete_workbase,
    get_workbase,
    list_workbases,
)


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


def _run_question(workbase_id: str, question: str, model: str | None, show_status: bool) -> tuple[str, list[dict]]:
    answer = ""
    sources: list[dict] = []
    for event in answer_message(workbase_id, question, model=model):
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
            f"score={source.get('score', 0.0):.3f}"
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

    answer, sources = _run_question(workbase["id"], args.question, args.model, not args.no_status)
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
        _, sources = _run_question(workbase["id"], question, args.model, not args.no_status)
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
    ask.set_defaults(func=cmd_ask)

    chat = subparsers.add_parser("chat", help="Start an interactive chat in a workbase.")
    chat.add_argument("workbase")
    chat.add_argument("--model")
    chat.add_argument("--no-status", action="store_true")
    chat.add_argument("--no-sources", action="store_true")
    chat.set_defaults(func=cmd_chat)

    doctor = subparsers.add_parser("doctor", help="Check local services and configuration.")
    doctor.add_argument("--query", default="machine learning definition")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
