from typing import Any

from fastapi import APIRouter, HTTPException

from research_assistant.workbases import add_report, delete_report, update_report
from research_assistant.writing import build_glossary, generate_article, generate_chapter

from .schemas import ReportCreate, ReportPatch
from .utils import normalize_retrieval_mode, report_to_api, require_workbase

router = APIRouter(tags=["reports"])


@router.get("/workbases/{workbase_id}/reports")
def list_reports(workbase_id: str) -> list[dict[str, Any]]:
    workbase = require_workbase(workbase_id)
    return [report_to_api(report, workbase) for report in workbase.get("reports", [])]


@router.post("/workbases/{workbase_id}/reports", status_code=201)
def create_workbase_report(workbase_id: str, payload: ReportCreate) -> dict[str, Any]:
    workbase = require_workbase(workbase_id)
    content = payload.content
    sources = payload.sources
    title = payload.title or payload.topic or payload.type
    if payload.generate != "none":
        generated = _generate_report(workbase_id, payload)
        content = generated.get("content", "")
        sources = generated.get("sources", [])
    report = add_report(workbase_id, title, payload.type, content, sources)
    if not report:
        raise HTTPException(status_code=400, detail="Could not create report")
    return report_to_api(report, workbase)


@router.get("/reports/{report_id}")
def get_report(report_id: str, workbase_id: str) -> dict[str, Any]:
    workbase = require_workbase(workbase_id)
    for report in workbase.get("reports", []):
        if report.get("id") == report_id:
            return report_to_api(report, workbase)
    raise HTTPException(status_code=404, detail="Report not found")


@router.patch("/reports/{report_id}")
def patch_report(report_id: str, payload: ReportPatch) -> dict[str, Any]:
    workbase = require_workbase(payload.workbase_id)
    updates = payload.model_dump(exclude_unset=True)
    updates.pop("workbase_id", None)
    report = update_report(payload.workbase_id, report_id, updates)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report_to_api(report, workbase)


@router.delete("/reports/{report_id}", status_code=204)
def remove_report(report_id: str, workbase_id: str) -> None:
    require_workbase(workbase_id)
    if not delete_report(workbase_id, report_id):
        raise HTTPException(status_code=404, detail="Report not found")


def _generate_report(workbase_id: str, payload: ReportCreate) -> dict[str, Any]:
    mode = normalize_retrieval_mode(payload.retrieval_mode)
    topic = payload.topic or payload.title
    if payload.generate == "article":
        return generate_article(
            workbase_id,
            topic,
            payload.audience,
            payload.tone,
            payload.length,
            payload.goal,
            retrieval_mode=mode,
            model=payload.model,
        )
    if payload.generate == "chapter":
        return generate_chapter(
            workbase_id,
            payload.title,
            payload.goal,
            payload.audience,
            payload.length,
            retrieval_mode=mode,
            model=payload.model,
        )
    return build_glossary(workbase_id, topic, retrieval_mode=mode, model=payload.model)
