from __future__ import annotations

import json
import re
from typing import Any, Iterable

from fastapi import HTTPException

from research_assistant.workbases import get_workbase


def normalize_retrieval_mode(value: str) -> str:
    if value == "all_sources":
        return "all"
    return value


def require_workbase(workbase_id: str) -> dict[str, Any]:
    workbase = get_workbase(workbase_id)
    if not workbase:
        raise HTTPException(status_code=404, detail="Workbase not found")
    return workbase


def chat_id_for(workbase_id: str) -> str:
    return f"{workbase_id}:default"


def workbase_id_from_chat(chat_id: str) -> str:
    return chat_id.rsplit(":default", 1)[0] if chat_id.endswith(":default") else chat_id


def message_to_api(message: dict[str, Any], index: int, chat_id: str) -> dict[str, Any]:
    return {
        "id": f"msg_{index + 1}",
        "chatId": chat_id,
        "role": message.get("role", "assistant"),
        "content": message.get("content", ""),
        "citations": sources_to_citations(message.get("sources", [])),
        "sources": message.get("sources", []),
        "createdAt": message.get("created_at", ""),
    }


def workbase_to_api(workbase: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": workbase["id"],
        "name": workbase.get("name", "Untitled Workbase"),
        "description": workbase.get("description", ""),
        "createdAt": workbase.get("created_at", ""),
        "updatedAt": workbase.get("updated_at", ""),
        "sourceCount": len(workbase.get("datasets", [])),
        "chatCount": 1 if workbase.get("messages") else 0,
        "chunkCount": workbase.get("chunk_count", 0),
        "reportCount": len(workbase.get("reports", [])),
    }


def source_to_api(source: dict[str, Any], workbase_id: str) -> dict[str, Any]:
    return {
        "id": source.get("document_id", ""),
        "workbaseId": workbase_id,
        "title": source.get("title") or "Untitled source",
        "type": source.get("file_type") or "web",
        "trustLevel": source.get("trust_level", "general_web"),
        "sourceOrigin": source.get("source_origin", "agent_web"),
        "tags": source.get("tags", []),
        "url": source.get("url") or "",
        "fileName": source.get("file_name") or "",
        "chunkCount": source.get("chunk_count", 0),
        "createdAt": source.get("date_added") or "",
        "updatedAt": source.get("date_added") or "",
        "datasetIds": source.get("dataset_ids", []),
        "parserName": source.get("parser_name", ""),
        "author": source.get("author", ""),
        "year": source.get("year", ""),
        "accessedDate": source.get("accessed_date", ""),
        "storedFilePath": source.get("stored_file_path", ""),
    }


def sources_to_citations(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations = []
    for index, source in enumerate(sources, start=1):
        citations.append(
            {
                "id": f"cit_{index}",
                "number": index,
                "sourceId": source.get("document_id") or source.get("source_id") or "",
                "title": source.get("title") or "Untitled source",
                "url": source.get("url") or "",
                "trustLevel": source.get("trust_level", "general_web"),
                "sourceOrigin": source.get("source_origin", "agent_web"),
                "excerpt": source.get("excerpt") or "",
                "datasetId": source.get("dataset_id") or "",
                "chunkIndex": source.get("chunk_index", 0),
                "score": source.get("score_final", source.get("score", 0)),
            }
        )
    return citations


def report_to_api(report: dict[str, Any], workbase: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": report.get("id", ""),
        "workbaseId": workbase["id"],
        "title": report.get("title", "Untitled report"),
        "type": report.get("type", "Research Summary"),
        "content": report.get("content", ""),
        "sources": report.get("sources", []),
        "createdAt": report.get("created_at", ""),
        "updatedAt": report.get("updated_at", report.get("created_at", "")),
        "workbaseName": workbase.get("name", "Workbase"),
    }


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def filename_slug(value: str, extension: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "sourcestack-export"
    return f"{safe}.{extension}"


def first(items: Iterable[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for item in items:
        if item.get(key) == value:
            return item
    return None
