import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings

METADATA_FILE = "metadata.json"


@dataclass
class WorkbaseResult:
    ok: bool
    workbase: dict[str, Any] | None = None
    error: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root() -> Path:
    path = settings.resolved_workbases_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def workbase_dir(workbase_id: str) -> Path:
    return _root() / workbase_id


def metadata_path(workbase_id: str) -> Path:
    return workbase_dir(workbase_id) / METADATA_FILE


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe or "workbase"


def create_workbase(name: str, description: str = "") -> WorkbaseResult:
    name = (name or "").strip()
    if not name:
        return WorkbaseResult(False, error="Workbase name is required.")

    workbase_id = f"{_slug(name)}-{uuid.uuid4().hex[:8]}"
    path = workbase_dir(workbase_id)
    path.mkdir(parents=True, exist_ok=False)

    metadata = {
        "id": workbase_id,
        "name": name,
        "description": description.strip(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "search_count": 0,
        "chunk_count": 0,
        "messages": [],
        "datasets": [],
    }
    save_workbase(metadata)
    return WorkbaseResult(True, workbase=metadata)


def save_workbase(metadata: dict[str, Any]) -> None:
    metadata["updated_at"] = now_iso()
    with metadata_path(metadata["id"]).open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)


def get_workbase(workbase_id: str) -> dict[str, Any] | None:
    path = metadata_path(workbase_id)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def list_workbases() -> list[dict[str, Any]]:
    workbases = []
    for path in _root().iterdir():
        meta_path = path / METADATA_FILE
        if meta_path.exists():
            try:
                with meta_path.open("r", encoding="utf-8") as file:
                    workbases.append(json.load(file))
            except Exception:
                continue
    return sorted(workbases, key=lambda item: item.get("updated_at", ""), reverse=True)


def delete_workbase(workbase_id: str) -> None:
    try:
        from .vector_store import delete_workbase_points

        delete_workbase_points(workbase_id)
    except Exception:
        pass

    path = workbase_dir(workbase_id)
    if path.exists():
        shutil.rmtree(path)


def add_message(workbase_id: str, role: str, content: str, sources: list[dict] | None = None) -> None:
    metadata = get_workbase(workbase_id)
    if not metadata:
        return
    message = {"role": role, "content": content, "created_at": now_iso()}
    if sources is not None:
        message["sources"] = sources
    metadata.setdefault("messages", []).append(message)
    save_workbase(metadata)


def next_dataset_id(workbase_id: str) -> str:
    metadata = get_workbase(workbase_id) or {}
    number = len(metadata.get("datasets", [])) + 1
    return f"dataset-{number:06d}"


def record_dataset(
    workbase_id: str,
    dataset_id: str,
    query: str | None,
    results: list[dict],
    chunks_added: int,
    total_chunks: int,
    dataset_type: str = "agent_web",
    chunks_updated: int = 0,
    duplicates_skipped: int = 0,
) -> None:
    metadata = get_workbase(workbase_id)
    if not metadata:
        return
    metadata.setdefault("datasets", []).append(
        {
            "dataset_id": dataset_id,
            "dataset_type": dataset_type,
            "query": query,
            "created_at": now_iso(),
            "sources": [
                {
                    "source_id": item.get("source_id"),
                    "document_id": item.get("document_id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "canonical_url": item.get("canonical_url"),
                    "position": item.get("position"),
                    "source_origin": item.get("source_origin"),
                    "trust_level": item.get("trust_level"),
                    "is_verified": item.get("is_verified"),
                    "scrape_status": item.get("scrape_status"),
                    "scrape_error": item.get("scrape_error"),
                    "parser_name": item.get("parser_name"),
                    "content_source": item.get("content_source"),
                    "file_type": item.get("file_type"),
                    "file_name": item.get("file_name"),
                    "tags": item.get("tags", []),
                    "author": item.get("author"),
                    "year": item.get("year"),
                    "accessed_date": item.get("accessed_date"),
                    "citation_key": item.get("citation_key"),
                }
                for item in results
            ],
            "chunks_added": chunks_added,
            "chunks_updated": chunks_updated,
            "duplicates_skipped": duplicates_skipped,
        }
    )
    metadata["search_count"] = len(metadata["datasets"])
    metadata["chunk_count"] = total_chunks
    save_workbase(metadata)


def refresh_chunk_count(workbase_id: str, total_chunks: int) -> None:
    metadata = get_workbase(workbase_id)
    if not metadata:
        return
    metadata["chunk_count"] = total_chunks
    save_workbase(metadata)


def conversation_history(workbase_id: str, limit: int = 12) -> list[dict[str, str]]:
    metadata = get_workbase(workbase_id) or {}
    messages = metadata.get("messages", [])[-limit:]
    return [
        {"role": item["role"], "content": item["content"]}
        for item in messages
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]
