import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    MatchAny,
    PointStruct,
    VectorParams,
)

from .config import settings
from .llm import embed

logger = logging.getLogger(__name__)


def _point_id(value: str) -> str:
    return str(uuid.UUID(value[:32]))


def client() -> QdrantClient:
    if settings.qdrant_api_key:
        return QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            check_compatibility=False,
        )
    return QdrantClient(url=settings.qdrant_url, check_compatibility=False)


def _workbase_filter(workbase_id: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(
                key="workbase_id",
                match=MatchValue(value=workbase_id),
            )
        ]
    )


def _retrieval_filter(
    workbase_id: str,
    retrieval_mode: str = "all",
    document_id: str | None = None,
    tags: list[str] | None = None,
) -> Filter:
    conditions = [
        FieldCondition(
            key="workbase_id",
            match=MatchValue(value=workbase_id),
        )
    ]
    if retrieval_mode == "curated_trusted":
        conditions.append(
            FieldCondition(
                key="trust_level",
                match=MatchAny(any=["curated", "trusted_domain"]),
            )
        )
    elif retrieval_mode == "curated_only":
        conditions.append(
            FieldCondition(
                key="source_origin",
                match=MatchValue(value="manual_curation"),
            )
        )
    if document_id:
        conditions.append(FieldCondition(key="document_id", match=MatchValue(value=document_id)))
    if tags:
        conditions.append(FieldCondition(key="tags", match=MatchAny(any=tags)))
    return Filter(must=conditions)


def _collection_exists(store: QdrantClient) -> bool:
    try:
        store.get_collection(settings.qdrant_collection)
        return True
    except Exception:
        return False


def _collection_vector_size(store: QdrantClient) -> int | None:
    collection = store.get_collection(settings.qdrant_collection)
    vectors = collection.config.params.vectors
    return getattr(vectors, "size", None)


def ensure_collection(vector_size: int) -> None:
    store = client()
    if _collection_exists(store):
        existing_size = _collection_vector_size(store)
        if existing_size == vector_size:
            return

        point_count = store.count(settings.qdrant_collection, exact=True).count
        if point_count == 0:
            logger.warning(
                "Recreating empty Qdrant collection '%s' because vector size changed from %s to %s",
                settings.qdrant_collection,
                existing_size,
                vector_size,
            )
            store.delete_collection(settings.qdrant_collection)
        else:
            raise ValueError(
                f"Qdrant collection '{settings.qdrant_collection}' expects vectors of size "
                f"{existing_size}, but the current embedding model returned {vector_size}. "
                "Use an empty collection or migrate/re-embed existing points."
            )
    if _collection_exists(store):
        return

    store.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    logger.info(
        "Created Qdrant collection '%s' with vector size %s",
        settings.qdrant_collection,
        vector_size,
    )


def _payload_for_chunk(workbase_id: str, chunk: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    payload = {
        "workbase_id": workbase_id,
        "dataset_id": chunk["dataset_id"],
        "source_id": chunk["source_id"],
        "title": chunk.get("title", ""),
        "url": chunk.get("url", ""),
        "canonical_url": chunk.get("canonical_url", chunk.get("url", "")),
        "search_query": chunk.get("search_query", ""),
        "source_position": chunk.get("source_position", 0),
        "chunk_index": chunk.get("chunk_index", 0),
        "created_at": chunk.get("created_at", ""),
        "ingested_at": chunk.get("ingested_at", chunk.get("created_at", "")),
        "text": chunk["text"],
        "source_origin": chunk.get("source_origin", "agent_web"),
        "trust_level": chunk.get("trust_level", "general_web"),
        "is_verified": bool(chunk.get("is_verified", False)),
        "ingestion_method": chunk.get("ingestion_method", "search_web"),
        "parser_name": chunk.get("parser_name", ""),
        "parser_version": chunk.get("parser_version", ""),
        "document_id": chunk.get("document_id", ""),
        "source_fingerprint": chunk.get("source_fingerprint", ""),
        "content_hash": chunk.get("content_hash", ""),
        "file_name": chunk.get("file_name", ""),
        "file_type": chunk.get("file_type", ""),
        "stored_file_path": chunk.get("stored_file_path", ""),
        "embedding_model": chunk.get("embedding_model", settings.embedding_model),
        "embedding_dim": len(embedding),
        "section_h1": chunk.get("section_h1", ""),
        "section_h2": chunk.get("section_h2", ""),
        "section_h3": chunk.get("section_h3", ""),
        "notes": chunk.get("notes", ""),
        "tags": chunk.get("tags", []),
        "author": chunk.get("author", ""),
        "year": chunk.get("year", ""),
        "accessed_date": chunk.get("accessed_date", ""),
        "citation_key": chunk.get("citation_key", ""),
    }
    return {key: value for key, value in payload.items() if value is not None}


def _existing_payloads(store: QdrantClient, ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids or not _collection_exists(store):
        return {}
    records = store.retrieve(
        collection_name=settings.qdrant_collection,
        ids=[_point_id(point_id) for point_id in ids],
        with_payload=True,
        with_vectors=False,
    )
    return {str(record.id): record.payload or {} for record in records}


def upsert_chunks(workbase_id: str, chunks: list[dict[str, Any]]) -> dict[str, int]:
    stats = {"chunks_added": 0, "chunks_updated": 0, "duplicates_skipped": 0}
    if not chunks:
        return stats

    points: list[PointStruct] = []
    vector_size: int | None = None
    store = client()
    existing = _existing_payloads(store, [chunk["id"] for chunk in chunks])

    for chunk in chunks:
        point_uuid = _point_id(chunk["id"])
        current_payload = existing.get(point_uuid)
        if current_payload and current_payload.get("content_hash") == chunk.get("content_hash"):
            stats["duplicates_skipped"] += 1
            continue

        embedding = embed(chunk["text"])
        if not embedding:
            continue
        vector_size = vector_size or len(embedding)
        if current_payload:
            stats["chunks_updated"] += 1
        else:
            stats["chunks_added"] += 1
        points.append(
            PointStruct(
                id=point_uuid,
                vector=embedding,
                payload=_payload_for_chunk(workbase_id, chunk, embedding),
            )
        )

    if not points or vector_size is None:
        return stats

    ensure_collection(vector_size)
    client().upsert(collection_name=settings.qdrant_collection, points=points)
    return stats


def add_chunks(workbase_id: str, chunks: list[dict[str, Any]]) -> int:
    stats = upsert_chunks(workbase_id, chunks)
    return stats["chunks_added"] + stats["chunks_updated"]


def search(
    workbase_id: str,
    query: str,
    limit: int,
    retrieval_mode: str = "all",
    document_id: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    store = client()
    if not _collection_exists(store):
        return []

    query_embedding = embed(query)
    if not query_embedding:
        return []

    ensure_collection(len(query_embedding))

    try:
        response = store.query_points(
            collection_name=settings.qdrant_collection,
            query=query_embedding,
            query_filter=_retrieval_filter(workbase_id, retrieval_mode, document_id=document_id, tags=tags),
            limit=limit,
            with_payload=True,
        )
    except UnexpectedResponse as exc:
        logger.warning("Qdrant search failed: %s", exc)
        return []

    rows: list[dict[str, Any]] = []
    for item in response.points:
        payload = item.payload or {}
        rows.append(
            {
                "id": item.id,
                "text": payload.get("text", ""),
                "metadata": payload,
                "score": item.score,
            }
        )
    return rows


def count(workbase_id: str) -> int:
    store = client()
    if not _collection_exists(store):
        return 0

    response = store.count(
        collection_name=settings.qdrant_collection,
        count_filter=_workbase_filter(workbase_id),
        exact=True,
    )
    return response.count


def delete_workbase_points(workbase_id: str) -> None:
    store = client()
    if not _collection_exists(store):
        return
    store.delete(
        collection_name=settings.qdrant_collection,
        points_selector=_workbase_filter(workbase_id),
    )


def delete_document_points(workbase_id: str, document_id: str) -> None:
    store = client()
    if not _collection_exists(store):
        return
    store.delete(
        collection_name=settings.qdrant_collection,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(key="workbase_id", match=MatchValue(value=workbase_id)),
                    FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                ]
            )
        ),
    )


def delete_source_document(workbase_id: str, document_id: str) -> int:
    removed = len(document_payloads(workbase_id, document_id))
    delete_document_points(workbase_id, document_id)
    try:
        from .workbases import refresh_chunk_count

        refresh_chunk_count(workbase_id, count(workbase_id))
    except Exception:
        pass
    return removed


def document_payloads(workbase_id: str, document_id: str) -> list[dict[str, Any]]:
    store = client()
    if not _collection_exists(store):
        return []
    records, _ = store.scroll(
        collection_name=settings.qdrant_collection,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="workbase_id", match=MatchValue(value=workbase_id)),
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
            ]
        ),
        limit=10000,
        with_payload=True,
        with_vectors=False,
    )
    return [record.payload or {} for record in records]


def source_documents(workbase_id: str) -> list[dict[str, Any]]:
    store = client()
    if not _collection_exists(store):
        return []
    records, _ = store.scroll(
        collection_name=settings.qdrant_collection,
        scroll_filter=_workbase_filter(workbase_id),
        limit=10000,
        with_payload=True,
        with_vectors=False,
    )
    by_document: dict[str, dict[str, Any]] = {}
    for record in records:
        payload = record.payload or {}
        document_id = payload.get("document_id") or payload.get("source_id") or str(record.id)
        entry = by_document.setdefault(
            document_id,
            {
                "document_id": document_id,
                "title": payload.get("title", "Untitled"),
                "url": payload.get("canonical_url") or payload.get("url", ""),
                "file_name": payload.get("file_name", ""),
                "file_type": payload.get("file_type") or ("url" if payload.get("url") else "web"),
                "stored_file_path": payload.get("stored_file_path", ""),
                "source_origin": payload.get("source_origin", "agent_web"),
                "trust_level": payload.get("trust_level", "general_web"),
                "is_verified": payload.get("is_verified", False),
                "dataset_ids": set(),
                "chunk_count": 0,
                "date_added": payload.get("ingested_at") or payload.get("created_at", ""),
                "parser_name": payload.get("parser_name", ""),
                "tags": set(payload.get("tags") or []),
                "author": payload.get("author", ""),
                "year": payload.get("year", ""),
                "accessed_date": payload.get("accessed_date", ""),
                "citation_key": payload.get("citation_key", ""),
            },
        )
        entry["chunk_count"] += 1
        if payload.get("dataset_id"):
            entry["dataset_ids"].add(payload["dataset_id"])
        if payload.get("ingested_at") or payload.get("created_at"):
            dates = [entry["date_added"], payload.get("ingested_at") or payload.get("created_at")]
            entry["date_added"] = min(value for value in dates if value)
        entry["tags"].update(payload.get("tags") or [])
    results = []
    for entry in by_document.values():
        entry["dataset_ids"] = sorted(entry["dataset_ids"])
        entry["tags"] = sorted(entry["tags"])
        results.append(entry)
    return sorted(results, key=lambda item: item.get("date_added", ""), reverse=True)


def update_document_metadata(workbase_id: str, document_id: str, updates: dict[str, Any]) -> int:
    payloads = document_payloads(workbase_id, document_id)
    if not payloads:
        return 0
    store = client()
    records, _ = store.scroll(
        collection_name=settings.qdrant_collection,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="workbase_id", match=MatchValue(value=workbase_id)),
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
            ]
        ),
        limit=10000,
        with_payload=False,
        with_vectors=False,
    )
    ids = [record.id for record in records]
    if ids:
        store.set_payload(collection_name=settings.qdrant_collection, payload=updates, points=ids)
    return len(ids)
