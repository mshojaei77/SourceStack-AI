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


def _budget_int(name: str, normal: int, budget: int) -> int:
    if os.getenv(name) is not None:
        return int(os.getenv(name, str(normal)))
    return budget if _bool("BUDGET_MODE", False) else normal


DEFAULT_TECHNICAL_DOMAIN_WHITELIST = [
    "arxiv.org",
    "github.com",
    "huggingface.co",
    "openai.com",
    "platform.openai.com",
    "docs.anthropic.com",
    "anthropic.com",
    "pytorch.org",
    "tensorflow.org",
    "qdrant.tech",
    "langchain.com",
    "python.org",
    "microsoft.com",
    "learn.microsoft.com",
    "developer.mozilla.org",
]


@dataclass(frozen=True)
class Settings:
    app_root: Path = Path(__file__).resolve().parents[2]
    workbases_dir: Path = Path(os.getenv("WORKBASES_DIR", "data/workspaces"))

    searxng_url: str = os.getenv("SEARXNG_URL", "http://localhost:8080")
    searxng_results: int = int(os.getenv("SEARXNG_RESULTS", "5"))
    searxng_engines: str = os.getenv("SEARXNG_ENGINES", "bing")
    scrape_max_chars: int = int(os.getenv("SCRAPE_MAX_CHARS", "10000"))
    scrape_playwright: bool = _bool("SCRAPE_PLAYWRIGHT", False)
    technical_mode: bool = _bool("TECHNICAL_MODE", False)
    technical_domain_whitelist_raw: str = os.getenv(
        "TECHNICAL_DOMAIN_WHITELIST",
        ",".join(DEFAULT_TECHNICAL_DOMAIN_WHITELIST),
    )

    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY") or None
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "workbase_chunks")

    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    llm_provider: str = os.getenv("LLM_PROVIDER", "openrouter")
    generation_model: str = os.getenv("GENERATION_MODEL", os.getenv("LLM_MODEL_DEFAULT", "google/gemini-3-flash-preview"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "google/gemini-embedding-001")
    enable_model_routing: bool = _bool("ENABLE_MODEL_ROUTING", True)
    budget_mode: bool = _bool("BUDGET_MODE", False)
    model_small: str = os.getenv("LLM_MODEL_SMALL", os.getenv("LLM_MODEL_PLANNER", generation_model))
    model_default: str = os.getenv("LLM_MODEL_DEFAULT", generation_model)
    model_strong: str = os.getenv("LLM_MODEL_STRONG", os.getenv("LLM_MODEL_FINAL", generation_model))
    model_planner: str = os.getenv("LLM_MODEL_PLANNER", model_small)
    model_query_rewrite: str = os.getenv("LLM_MODEL_QUERY_REWRITE", model_planner)
    model_metadata: str = os.getenv("LLM_MODEL_METADATA", model_planner)
    model_final: str = os.getenv("LLM_MODEL_FINAL", model_default)
    model_deep_reasoning: str = os.getenv("LLM_MODEL_DEEP_REASONING", model_strong)
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "openrouter")
    debug_costs: bool = _bool("DEBUG_COSTS", False)

    local: bool = _bool("LOCAL", False)
    local_base_url: str = os.getenv("LOCAL_BASE_URL", "http://localhost:8000/v1")
    local_generation_model: str = os.getenv("LOCAL_GENERATION_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
    local_embedding_model: str = os.getenv("LOCAL_EMBEDDING_MODEL", "Octen/Octen-Embedding-8B")

    reranker_enabled: bool = _bool("RERANKER", True)
    reranker_provider: str = os.getenv("RERANKER_PROVIDER", "local")
    reranker_model: str = os.getenv("RERANKER_MODEL", "jinaai/jina-reranker-v3")
    reranker_candidate_limit: int = _budget_int(
        "RETRIEVAL_CANDIDATE_K",
        int(os.getenv("RERANKER_CANDIDATE_LIMIT", "24")),
        30,
    )
    reranker_top_k: int = _budget_int("FINAL_CONTEXT_K", int(os.getenv("RERANKER_TOP_K", "8")), 8)
    authority_boost_curated: float = float(os.getenv("AUTHORITY_BOOST_CURATED", "1.35"))
    authority_boost_trusted_domain: float = float(os.getenv("AUTHORITY_BOOST_TRUSTED_DOMAIN", "1.15"))
    authority_boost_general_web: float = float(os.getenv("AUTHORITY_BOOST_GENERAL_WEB", "1.0"))

    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1400"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "220"))
    max_search_results: int = _budget_int("MAX_SEARCH_RESULTS", searxng_results, 5)
    max_scrape_pages: int = _budget_int("MAX_SCRAPE_PAGES", searxng_results, 5)

    @property
    def generation_model_options(self) -> list[str]:
        options = _csv("GENERATION_MODEL_OPTIONS")
        if self.generation_model not in options:
            options.insert(0, self.generation_model)
        return options

    @property
    def technical_domain_whitelist(self) -> list[str]:
        return [domain.lower().strip() for domain in self.technical_domain_whitelist_raw.split(",") if domain.strip()]

    @property
    def authority_boosts(self) -> dict[str, float]:
        return {
            "curated": self.authority_boost_curated,
            "trusted_domain": self.authority_boost_trusted_domain,
            "general_web": self.authority_boost_general_web,
        }

    @property
    def resolved_workbases_dir(self) -> Path:
        if self.workbases_dir.is_absolute():
            return self.workbases_dir
        return self.app_root / self.workbases_dir


settings = Settings()
