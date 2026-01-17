"""
Jobs API routes - Status polling for background tasks
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db.database import get_db
from app.db.models import Job

router = APIRouter()


class JobResponse(BaseModel):
    id: int
    type: str
    status: str
    progress: int
    total_items: int
    processed_items: int
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """Get status of a background job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.get("/", response_model=List[JobResponse])
def list_jobs(limit: int = 20, db: Session = Depends(get_db)):
    """List recent jobs"""
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(limit).all()
    return jobs
