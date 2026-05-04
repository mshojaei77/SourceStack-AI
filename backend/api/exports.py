from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from research_assistant.citations import build_export_markdown
from research_assistant.exporting import markdown_to_pdf

from .schemas import ExportCreate
from .utils import filename_slug

router = APIRouter(tags=["exports"])


@router.post("/exports/markdown")
def export_markdown(payload: ExportCreate) -> Response:
    markdown = build_export_markdown(payload.title, payload.content, payload.sources, payload.workbase_name)
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename_slug(payload.title, "md")}"'},
    )


@router.post("/exports/pdf")
def export_pdf(payload: ExportCreate) -> Response:
    markdown = build_export_markdown(payload.title, payload.content, payload.sources, payload.workbase_name)
    pdf, error = markdown_to_pdf(markdown, payload.title)
    if not pdf:
        raise HTTPException(status_code=503, detail=error)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename_slug(payload.title, "pdf")}"'},
    )


@router.get("/exports/{export_id}/download")
def download_export(export_id: str) -> dict[str, str]:
    return {
        "status": "unavailable",
        "message": "Exports are generated on demand. Use POST /api/exports/markdown or /api/exports/pdf.",
        "export_id": export_id,
    }
