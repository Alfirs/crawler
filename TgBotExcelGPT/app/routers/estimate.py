from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services import estimate_pipeline, google_drive

router = APIRouter(prefix="/estimate", tags=["estimate"])


@router.post("/final")
async def upload_final_estimate(
    project_id: str = Form(...),
    notes: Optional[str] = Form(None),
    file: UploadFile = File(...),
) -> dict:
    if not file:
        raise HTTPException(status_code=400, detail="File is required")

    drive_link = await google_drive.save_upload(project_id, file)
    validation = await estimate_pipeline.validate_final_estimate(project_id, drive_link)
    normalized = await estimate_pipeline.normalize_materials(project_id, drive_link)

    return {
        "project_id": project_id,
        "file_saved": drive_link,
        "validation": validation,
        "normalized": normalized,
        "notes": notes,
    }
