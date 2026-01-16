from fastapi import APIRouter, HTTPException

from app.services import project_store

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/")
async def list_projects() -> dict:
    return {"projects": project_store.list_projects()}


@router.get("/{project_id}/summary")
async def project_summary(project_id: str) -> dict:
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail="project_not_found")
    return project_store.summary(project_id)
