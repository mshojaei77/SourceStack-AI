import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
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


def add_chunks(workbase_id: str, chunks: list[dict[str, Any]]) -> int:
    if not chunks:
        return 0

    points: list[PointStruct] = []
    vector_size: int | None = None

    for chunk in chunks:
        embedding = embed(chunk["text"])
        if not embedding:
            continue
        vector_size = vector_size or len(embedding)
        points.append(
            PointStruct(
                id=_point_id(chunk["id"]),
                vector=embedding,
                payload={
                    "workbase_id": workbase_id,
                    "dataset_id": chunk["dataset_id"],
                    "source_id": chunk["source_id"],
                    "title": chunk.get("title", ""),
                    "url": chunk.get("url", ""),
                    "search_query": chunk.get("search_query", ""),
                    "source_position": chunk.get("source_position", 0),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "created_at": chunk.get("created_at", ""),
                    "text": chunk["text"],
                },
            )
        )

    if not points or vector_size is None:
        return 0

    ensure_collection(vector_size)
    client().upsert(collection_name=settings.qdrant_collection, points=points)
    return len(points)


def search(workbase_id: str, query: str, limit: int) -> list[dict[str, Any]]:
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
            query_filter=_workbase_filter(workbase_id),
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
