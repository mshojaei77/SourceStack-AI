from typing import Any

from fastapi import APIRouter

from research_assistant.config import settings

from .schemas import SettingsPatch
from .utils import require_workbase

router = APIRouter(tags=["settings"])


RUNTIME_SETTINGS: dict[str, Any] = {
    "answerStyle": "Simple",
    "retrievalMode": "curated_trusted",
    "citationStyle": "numbered",
    "citationsEnabled": True,
    "technicalMode": settings.technical_mode,
    "budgetMode": settings.budget_mode,
    "modelPreset": "balanced",
    "advancedMode": False,
    "theme": "system",
}


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    return {
        **RUNTIME_SETTINGS,
        "backend": {
            "searxngUrl": settings.searxng_url,
            "qdrantUrl": settings.qdrant_url,
            "qdrantCollection": settings.qdrant_collection,
            "embeddingModel": settings.embedding_model,
            "rerankerModel": settings.reranker_model,
            "retrievalCandidateCount": settings.reranker_candidate_limit,
            "finalContextChunks": settings.reranker_top_k,
            "chunkSize": settings.chunk_size,
            "chunkOverlap": settings.chunk_overlap,
            "trustedDomainWhitelist": settings.technical_domain_whitelist,
            "pdfExportAvailable": _pdf_export_available(),
        },
    }


@router.patch("/settings")
def patch_settings(payload: SettingsPatch) -> dict[str, Any]:
    RUNTIME_SETTINGS.update(payload.values)
    return get_settings()


@router.get("/model-presets")
def model_presets() -> list[dict[str, Any]]:
    return [
        {"id": "cheapest", "label": "Cheapest", "model": settings.model_small},
        {"id": "balanced", "label": "Balanced", "model": settings.model_default},
        {"id": "best_quality", "label": "Best Quality", "model": settings.model_strong},
        {"id": "custom", "label": "Custom", "model": settings.generation_model},
    ]


@router.patch("/workbases/{workbase_id}/settings")
def patch_workbase_settings(workbase_id: str, payload: SettingsPatch) -> dict[str, Any]:
    workbase = require_workbase(workbase_id)
    workbase.setdefault("settings", {}).update(payload.values)
    from research_assistant.workbases import save_workbase

    save_workbase(workbase)
    return workbase["settings"]


def _pdf_export_available() -> bool:
    from research_assistant.exporting import pandoc_available

    return pandoc_available()
