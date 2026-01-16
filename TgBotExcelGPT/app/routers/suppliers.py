from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import pricing, project_store, suppliers as supplier_service

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


class SupplierRequestPayload(BaseModel):
    project_id: str
    max_api_suppliers: int = 3


@router.post("/request")
async def request_suppliers(payload: SupplierRequestPayload) -> dict:
    materials = project_store.load_items(payload.project_id, "procurement")
    if not materials:
        raise HTTPException(status_code=400, detail="Procurement list not ready")

    dispatch = await supplier_service.dispatch_requests(
        project_id=payload.project_id,
        materials=materials,
        max_api_suppliers=payload.max_api_suppliers,
    )
    summary = pricing.build_summary(payload.project_id)
    return {"dispatch": dispatch, "summary": summary}


@router.get("/summary/{project_id}")
async def supplier_summary(project_id: str) -> dict:
    summary = pricing.build_summary(project_id)
    return summary
