import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_root: Path = Path(__file__).resolve().parents[2]
    workbases_dir: Path = Path(os.getenv("WORKBASES_DIR", "data/workspaces"))

    searxng_url: str = os.getenv("SEARXNG_URL", "http://localhost:8080")
    searxng_results: int = int(os.getenv("SEARXNG_RESULTS", "5"))
    searxng_engines: str = os.getenv("SEARXNG_ENGINES", "bing")
    scrape_max_chars: int = int(os.getenv("SCRAPE_MAX_CHARS", "10000"))
    scrape_playwright: bool = _bool("SCRAPE_PLAYWRIGHT", False)

    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY") or None
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "workbase_chunks")

    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    generation_model: str = os.getenv("GENERATION_MODEL", "google/gemini-3-flash-preview")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "google/gemini-embedding-001")

    local: bool = _bool("LOCAL", False)
    local_base_url: str = os.getenv("LOCAL_BASE_URL", "http://localhost:8000/v1")
    local_generation_model: str = os.getenv("LOCAL_GENERATION_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
    local_embedding_model: str = os.getenv("LOCAL_EMBEDDING_MODEL", "Octen/Octen-Embedding-8B")

    reranker_enabled: bool = _bool("RERANKER", True)
    reranker_model: str = os.getenv("RERANKER_MODEL", "jinaai/jina-reranker-v3")
    reranker_candidate_limit: int = int(os.getenv("RERANKER_CANDIDATE_LIMIT", "24"))
    reranker_top_k: int = int(os.getenv("RERANKER_TOP_K", "8"))

    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1400"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "220"))

    @property
    def generation_model_options(self) -> list[str]:
        options = _csv("GENERATION_MODEL_OPTIONS")
        if self.generation_model not in options:
            options.insert(0, self.generation_model)
        return options

    @property
    def resolved_workbases_dir(self) -> Path:
        if self.workbases_dir.is_absolute():
            return self.workbases_dir
        return self.app_root / self.workbases_dir


settings = Settings()
