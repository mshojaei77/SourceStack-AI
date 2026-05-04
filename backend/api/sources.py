import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from research_assistant.manual_ingest import ingest_file, ingest_url
from research_assistant.rag_pipeline import answer_message
from research_assistant.vector_store import (
    delete_source_document,
    document_payloads,
    source_documents,
    update_document_metadata,
)

from .schemas import SourceAskCreate, SourcePatch, UrlIngestCreate
from .utils import first, normalize_retrieval_mode, require_workbase, source_to_api, sources_to_citations

router = APIRouter(tags=["sources"])


@router.get("/workbases/{workbase_id}/sources")
def list_sources(workbase_id: str) -> list[dict[str, Any]]:
    require_workbase(workbase_id)
    return [source_to_api(source, workbase_id) for source in source_documents(workbase_id)]


@router.post("/workbases/{workbase_id}/sources/upload", status_code=201)
async def upload_source(
    workbase_id: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    notes: str = Form(""),
    tags: str = Form(""),
) -> dict[str, Any]:
    require_workbase(workbase_id)
    suffix = Path(file.filename or "source.txt").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(await file.read())
        temp_path = Path(temp.name)
    try:
        result = ingest_file(
            workbase_id,
            temp_path,
            title=title,
            notes=notes,
            source_name=file.filename,
            tags=[item.strip() for item in tags.split(",") if item.strip()],
        )
    finally:
        temp_path.unlink(missing_ok=True)
    return result


@router.post("/workbases/{workbase_id}/sources/url", status_code=201)
def add_url_source(workbase_id: str, payload: UrlIngestCreate) -> dict[str, Any]:
    require_workbase(workbase_id)
    return ingest_url(
        workbase_id,
        payload.url,
        title=payload.title,
        notes=payload.notes,
        tags=payload.tags,
        citation=payload.citation,
    )


@router.get("/sources/{source_id}")
def get_source(source_id: str, workbase_id: str) -> dict[str, Any]:
    require_workbase(workbase_id)
    source = first(source_documents(workbase_id), "document_id", source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    data = source_to_api(source, workbase_id)
    data["chunks"] = document_payloads(workbase_id, source_id)
    return data


@router.patch("/sources/{source_id}")
def patch_source(source_id: str, payload: SourcePatch) -> dict[str, Any]:
    require_workbase(payload.workbase_id)
    updates = {
        key: value
        for key, value in {
            "title": payload.title,
            "tags": payload.tags,
            "author": payload.author,
            "year": payload.year,
            "url": payload.url,
            "canonical_url": payload.url,
        }.items()
        if value is not None
    }
    changed = update_document_metadata(payload.workbase_id, source_id, updates)
    if not changed:
        raise HTTPException(status_code=404, detail="Source not found")
    source = first(source_documents(payload.workbase_id), "document_id", source_id)
    return source_to_api(source or {"document_id": source_id}, payload.workbase_id)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: str, workbase_id: str) -> None:
    require_workbase(workbase_id)
    delete_source_document(workbase_id, source_id)


@router.post("/sources/{source_id}/reingest")
def reingest_source(source_id: str, workbase_id: str) -> dict[str, Any]:
    require_workbase(workbase_id)
    source = first(source_documents(workbase_id), "document_id", source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.get("stored_file_path") and Path(source["stored_file_path"]).exists():
        return ingest_file(
            workbase_id,
            source["stored_file_path"],
            title=source.get("title", ""),
            source_name=source.get("file_name") or Path(source["stored_file_path"]).name,
            tags=source.get("tags", []),
        )
    if source.get("url"):
        return ingest_url(workbase_id, source["url"], title=source.get("title", ""), tags=source.get("tags", []))
    raise HTTPException(status_code=400, detail="No stored file or URL is available for this source")


@router.post("/sources/{source_id}/ask")
def ask_source(source_id: str, payload: SourceAskCreate) -> dict[str, Any]:
    require_workbase(payload.workbase_id)
    content = ""
    sources: list[dict[str, Any]] = []
    for event in answer_message(
        payload.workbase_id,
        payload.content,
        model=payload.model,
        technical_mode=payload.technical_mode,
        retrieval_mode=normalize_retrieval_mode(payload.retrieval_mode),
        answer_style=payload.answer_style,
        document_id=source_id,
        tags=payload.tags,
    ):
        if event["type"] == "token":
            content += event["content"]
        elif event["type"] == "sources":
            sources = event["content"]
    return {"content": content, "citations": sources_to_citations(sources), "sources": sources}
