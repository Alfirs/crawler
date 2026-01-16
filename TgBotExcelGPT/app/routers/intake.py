from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services import google_drive, intake_pipeline

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("/files")
async def upload_files(
    project_id: str = Form(...),
    is_specification: bool = Form(False),
    is_drawing: bool = Form(False),
    notes: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    drive_links = []
    for uploaded in files:
        link = await google_drive.save_upload(project_id, uploaded)
        drive_links.append(link)

    result = await intake_pipeline.process_upload(
        project_id=project_id,
        file_links=drive_links,
        is_specification=is_specification,
        is_drawing=is_drawing,
        notes=notes,
    )
    return {"project_id": project_id, "files_saved": drive_links, "result": result}
