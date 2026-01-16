from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.draft_post import DraftPost, DraftStatus
from app.schemas.drafts import DraftPostOut
from app.workers.job_queue import enqueue_publish_job, enqueue_sync_job

router = APIRouter(tags=["drafts"])


@router.post("/jobs/fetch_threads", status_code=status.HTTP_202_ACCEPTED)
def trigger_fetch_threads(topic: str = "ai", limit: int = Query(5, le=20, ge=1)):
    """Trigger async job that syncs top Threads posts."""

    enqueue_sync_job(topic=topic, limit=limit)
    return {"detail": "sync job enqueued"}


@router.get("/drafts", response_model=List[DraftPostOut])
def list_drafts(
    status_filter: DraftStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_session),
):
    """Return draft posts filtered by status when provided."""

    query = db.query(DraftPost)
    if status_filter:
        query = query.filter(DraftPost.status == status_filter)
    drafts = query.order_by(DraftPost.created_at.desc()).all()
    return [DraftPostOut.model_validate(d) for d in drafts]


@router.post("/drafts/{draft_id}/approve")
def approve_draft(draft_id: int, db: Session = Depends(get_session)):
    """Mark draft as approved and enqueue publish job."""

    draft = db.get(DraftPost, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft.status = DraftStatus.APPROVED
    db.commit()
    enqueue_publish_job(draft_id=draft_id)
    return {"detail": "draft approved"}


@router.post("/drafts/{draft_id}/reject")
def reject_draft(draft_id: int, db: Session = Depends(get_session)):
    """Mark draft as rejected."""

    draft = db.get(DraftPost, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft.status = DraftStatus.REJECTED
    db.commit()
    return {"detail": "draft rejected"}
