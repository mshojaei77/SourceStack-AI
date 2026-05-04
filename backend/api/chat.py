from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from research_assistant.rag_pipeline import answer_message
from research_assistant.workbases import get_workbase, save_workbase

from .schemas import ChatCreate, ChatMessageCreate
from .utils import (
    chat_id_for,
    message_to_api,
    normalize_retrieval_mode,
    require_workbase,
    sources_to_citations,
    sse,
    workbase_id_from_chat,
)

router = APIRouter(tags=["chat"])


@router.get("/workbases/{workbase_id}/chats")
def list_chats(workbase_id: str) -> list[dict[str, Any]]:
    workbase = require_workbase(workbase_id)
    messages = workbase.get("messages", [])
    title = next((item.get("content", "")[:64] for item in messages if item.get("role") == "user"), "Research Chat")
    return [
        {
            "id": chat_id_for(workbase_id),
            "workbaseId": workbase_id,
            "title": title or "Research Chat",
            "createdAt": workbase.get("created_at", ""),
            "updatedAt": workbase.get("updated_at", ""),
            "messageCount": len(messages),
        }
    ]


@router.post("/workbases/{workbase_id}/chats", status_code=201)
def create_chat(workbase_id: str, payload: ChatCreate) -> dict[str, Any]:
    workbase = require_workbase(workbase_id)
    return {
        "id": chat_id_for(workbase_id),
        "workbaseId": workbase_id,
        "title": payload.title or "Research Chat",
        "createdAt": workbase.get("created_at", ""),
        "updatedAt": workbase.get("updated_at", ""),
        "messageCount": len(workbase.get("messages", [])),
    }


@router.get("/chats/{chat_id}")
def get_chat(chat_id: str) -> dict[str, Any]:
    workbase_id = workbase_id_from_chat(chat_id)
    workbase = require_workbase(workbase_id)
    messages = [
        message_to_api(message, index, chat_id_for(workbase_id))
        for index, message in enumerate(workbase.get("messages", []))
    ]
    return {
        "id": chat_id_for(workbase_id),
        "workbaseId": workbase_id,
        "title": workbase.get("name", "Research Chat"),
        "messages": messages,
    }


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str) -> None:
    workbase_id = workbase_id_from_chat(chat_id)
    workbase = require_workbase(workbase_id)
    workbase["messages"] = []
    save_workbase(workbase)


@router.post("/chats/{chat_id}/messages")
def create_message(chat_id: str, payload: ChatMessageCreate) -> dict[str, Any]:
    workbase_id = workbase_id_from_chat(chat_id)
    content = ""
    sources: list[dict[str, Any]] = []
    for event in answer_message(
        workbase_id,
        payload.content,
        model=payload.model,
        technical_mode=payload.technical_mode,
        retrieval_mode=normalize_retrieval_mode(payload.retrieval_mode),
        answer_style=payload.answer_style,
        document_id=payload.document_id,
        tags=payload.tags,
    ):
        if event["type"] == "token":
            content += event["content"]
        elif event["type"] == "sources":
            sources = event["content"]
    return {
        "message_id": f"msg_{uuid4().hex[:12]}",
        "content": content,
        "citations": sources_to_citations(sources),
        "references": [
            {"number": index, "label": f"[{source.get('trust_level', 'Web')}] {source.get('title', 'Untitled')}"}
            for index, source in enumerate(sources, start=1)
        ],
        "sources": sources,
        "usage": {},
    }


@router.post("/chats/{chat_id}/messages/stream")
def stream_message(chat_id: str, payload: ChatMessageCreate) -> StreamingResponse:
    workbase_id = workbase_id_from_chat(chat_id)

    def generate():
        sources: list[dict[str, Any]] = []
        saw_token = False
        try:
            yield sse("status", {"message": "Finding relevant sources..."})
            for event in answer_message(
                workbase_id,
                payload.content,
                model=payload.model,
                technical_mode=payload.technical_mode,
                retrieval_mode=normalize_retrieval_mode(payload.retrieval_mode),
                answer_style=payload.answer_style,
                document_id=payload.document_id,
                tags=payload.tags,
            ):
                if event["type"] == "status":
                    message = event["content"] if payload.advanced_mode else _friendly_status(event["content"], saw_token)
                    if message:
                        yield sse("status", {"message": message})
                elif event["type"] == "token":
                    saw_token = True
                    yield sse("token", {"text": event["content"]})
                elif event["type"] == "sources":
                    sources = event["content"]
                    yield sse("citations", {"citations": sources_to_citations(sources), "sources": sources})
            yield sse("done", {"message_id": f"msg_{uuid4().hex[:12]}"})
        except Exception as exc:
            yield sse("error", {"message": "Something went wrong while generating the answer.", "detail": str(exc)})

    return StreamingResponse(generate(), media_type="text/event-stream")


def _friendly_status(raw: str, saw_token: bool) -> str:
    lowered = raw.lower()
    if saw_token:
        return ""
    if "retriev" in lowered:
        return "Reading your sources..."
    if "running langgraph" in lowered or "stored" in lowered:
        return "Finding relevant sources..."
    if "writing" in lowered:
        return "Writing answer..."
    return ""
