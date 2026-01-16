from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import final_report, notifications, project_store

router = APIRouter(prefix="/reports", tags=["reports"])


class FinalReportPayload(BaseModel):
    project_id: str


class NotifyPayload(BaseModel):
    project_id: str
    emails: Optional[List[str]] = None
    telegram_ids: Optional[List[str]] = None


@router.post("/final")
async def build_final_report(payload: FinalReportPayload) -> dict:
    result = final_report.prepare_final_report(payload.project_id)
    if result.get("status") != "ready":
        raise HTTPException(status_code=400, detail=result.get("status"))
    return result


@router.post("/notify")
async def notify_final_report(payload: NotifyPayload) -> dict:
    result = final_report.prepare_final_report(payload.project_id)
    if result.get("status") != "ready":
        raise HTTPException(status_code=400, detail="Final report is not ready")
    entry = await notifications.send_summary(
        project_id=payload.project_id,
        artifact=result.get("artifact", {}),
        emails=payload.emails or [],
        telegram_ids=payload.telegram_ids or [],
    )
    return {"notification": entry, "report": result}
