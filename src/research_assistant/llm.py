import logging
import json
import hashlib
from typing import Any

from openai import OpenAI

from .config import settings

logger = logging.getLogger(__name__)
_embedding_cache: dict[str, list[float]] | None = None


def _client() -> OpenAI:
    if settings.local:
        return OpenAI(base_url=settings.local_base_url, api_key="local")
    return OpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)


def generation_model(model: str | None = None, task: str = "final") -> str:
    if model:
        return model
    if settings.local:
        return settings.local_generation_model
    if not settings.enable_model_routing:
        return settings.generation_model
    task_models = {
        "planner": settings.model_planner,
        "query_rewrite": settings.model_query_rewrite,
        "metadata": settings.model_metadata,
        "final": settings.model_final,
        "deep_reasoning": settings.model_deep_reasoning,
    }
    return task_models.get(task, settings.model_final)


def embedding_model() -> str:
    return settings.local_embedding_model if settings.local else settings.embedding_model


def _cache_path():
    path = settings.resolved_workbases_dir.parent / "embedding_cache.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{embedding_model()}:{digest}"


def _load_embedding_cache() -> dict[str, list[float]]:
    global _embedding_cache
    if _embedding_cache is not None:
        return _embedding_cache
    path = _cache_path()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as file:
                _embedding_cache = json.load(file)
                return _embedding_cache
        except Exception:
            logger.warning("Could not read embedding cache; starting fresh.")
    _embedding_cache = {}
    return _embedding_cache


def _save_embedding_cache(cache: dict[str, list[float]]) -> None:
    try:
        with _cache_path().open("w", encoding="utf-8") as file:
            json.dump(cache, file)
    except Exception as exc:
        logger.warning("Could not save embedding cache: %s", exc)


def route_report(final_override: str | None = None) -> dict[str, str]:
    return {
        "planner_model": generation_model(task="planner"),
        "final_model": generation_model(final_override, task="final"),
        "embedding_model": embedding_model(),
        "reranker_model": settings.reranker_model,
    }


def embed(text: str) -> list[float]:
    cache = _load_embedding_cache()
    key = _cache_key(text)
    if key in cache:
        return cache[key]
    try:
        response = _client().embeddings.create(model=embedding_model(), input=text)
        embedding = response.data[0].embedding
        cache[key] = embedding
        _save_embedding_cache(cache)
        return embedding
    except Exception as exc:
        logger.exception("Embedding failed: %s", exc)
        return []


def chat(
    messages: list[dict[str, Any]],
    model: str | None = None,
    tools: list[dict] | None = None,
    task: str = "final",
) -> dict:
    kwargs: dict[str, Any] = {
        "model": generation_model(model, task=task),
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = {"type": "function", "function": {"name": "search_web"}}

    try:
        response = _client().chat.completions.create(**kwargs)
        message = response.choices[0].message
        usage = getattr(response, "usage", None)
        return {
            "content": message.content or "",
            "model": kwargs["model"],
            "usage": {
                "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
            },
            "tool_calls": [
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                }
                for call in (message.tool_calls or [])
            ],
        }
    except Exception as exc:
        logger.exception("Chat completion failed: %s", exc)
        return {"content": f"Error: {exc}", "model": generation_model(model, task=task), "usage": {}, "tool_calls": []}


def stream_chat(messages: list[dict[str, Any]], model: str | None = None, task: str = "final"):
    try:
        stream = _client().chat.completions.create(
            model=generation_model(model, task=task),
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
    except Exception as exc:
        logger.exception("Streaming completion failed: %s", exc)
        yield f"Error: {exc}"
