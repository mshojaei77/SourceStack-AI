import logging
from typing import Any

from openai import OpenAI

from .config import settings

logger = logging.getLogger(__name__)


def _client() -> OpenAI:
    if settings.local:
        return OpenAI(base_url=settings.local_base_url, api_key="local")
    return OpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)


def generation_model(model: str | None = None) -> str:
    if model:
        return model
    return settings.local_generation_model if settings.local else settings.generation_model


def embedding_model() -> str:
    return settings.local_embedding_model if settings.local else settings.embedding_model


def embed(text: str) -> list[float]:
    try:
        response = _client().embeddings.create(model=embedding_model(), input=text)
        return response.data[0].embedding
    except Exception as exc:
        logger.exception("Embedding failed: %s", exc)
        return []


def chat(messages: list[dict[str, Any]], model: str | None = None, tools: list[dict] | None = None) -> dict:
    kwargs: dict[str, Any] = {
        "model": generation_model(model),
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = {"type": "function", "function": {"name": "search_web"}}

    try:
        response = _client().chat.completions.create(**kwargs)
        message = response.choices[0].message
        return {
            "content": message.content or "",
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
        return {"content": f"Error: {exc}", "tool_calls": []}


def stream_chat(messages: list[dict[str, Any]], model: str | None = None):
    try:
        stream = _client().chat.completions.create(
            model=generation_model(model),
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
