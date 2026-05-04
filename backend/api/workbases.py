from fastapi import APIRouter, HTTPException

from research_assistant.vector_store import source_documents
from research_assistant.workbases import (
    create_workbase,
    delete_workbase,
    get_workbase,
    list_workbases,
    save_workbase,
)

from .schemas import WorkbaseCreate, WorkbasePatch
from .utils import require_workbase, workbase_to_api

router = APIRouter(tags=["workbases"])


@router.get("/workbases")
def list_workbase_items() -> list[dict]:
    return [workbase_to_api(item) for item in list_workbases()]


@router.post("/workbases", status_code=201)
def create_workbase_item(payload: WorkbaseCreate) -> dict:
    result = create_workbase(payload.name, payload.description)
    if not result.ok or not result.workbase:
        raise HTTPException(status_code=400, detail=result.error or "Could not create Workbase")
    return workbase_to_api(result.workbase)


@router.get("/workbases/{workbase_id}")
def get_workbase_item(workbase_id: str) -> dict:
    workbase = require_workbase(workbase_id)
    data = workbase_to_api(workbase)
    data["messages"] = workbase.get("messages", [])
    data["reports"] = workbase.get("reports", [])
    data["sources"] = source_documents(workbase_id)
    return data


@router.patch("/workbases/{workbase_id}")
def patch_workbase_item(workbase_id: str, payload: WorkbasePatch) -> dict:
    workbase = require_workbase(workbase_id)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Workbase name is required")
        workbase["name"] = name
    if payload.description is not None:
        workbase["description"] = payload.description.strip()
    save_workbase(workbase)
    updated = get_workbase(workbase_id) or workbase
    return workbase_to_api(updated)


@router.delete("/workbases/{workbase_id}", status_code=204)
def delete_workbase_item(workbase_id: str) -> None:
    require_workbase(workbase_id)
    delete_workbase(workbase_id)
