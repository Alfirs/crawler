"""
Leads API routes - CRM functionality
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Lead, Message, Outreach, Note, Task, LeadStatus
from app.services.antispam import AntiSpamService
from app.services.gamification import GamificationService

router = APIRouter()


class LeadResponse(BaseModel):
    id: int
    workspace_id: int
    message_id: int
    type: str
    category: str
    target_professions: Optional[List[str]] = None
    fit_score: float
    money_score: float
    recency_score: float
    confidence: float
    total_score: float
    status: str
    do_not_contact: bool
    last_contacted_at: Optional[datetime]
    contact_count: int
    expected_revenue: Optional[float]
    lost_reason: Optional[str]
    created_at: datetime
    # Joined data
    message_text: Optional[str] = None
    message_author: Optional[str] = None
    message_date: Optional[datetime] = None
    outreach_count: int = 0
    notes_count: int = 0

    class Config:
        from_attributes = True


class LeadStatusUpdate(BaseModel):
    status: str
    lost_reason: Optional[str] = None
    expected_revenue: Optional[float] = None


class LeadDNCUpdate(BaseModel):
    do_not_contact: bool
    reason: Optional[str] = None


class NoteCreate(BaseModel):
    text: str


class TaskCreate(BaseModel):
    type: str = "FOLLOWUP"
    title: Optional[str] = None
    description: Optional[str] = None
    due_at: datetime


@router.get("/workspace/{workspace_id}", response_model=List[LeadResponse])
def list_leads(
    workspace_id: int,
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    profession: Optional[str] = Query(None, description="Filter by target profession"),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    sort_by: str = Query("total_score", pattern="^(total_score|created_at|status)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    include_dnc: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """List leads for a workspace with filtering and sorting"""
    query = db.query(Lead).options(
        joinedload(Lead.message)
    ).filter(Lead.workspace_id == workspace_id)
    
    # Apply filters
    if status:
        query = query.filter(Lead.status == status)
    if category:
        query = query.filter(Lead.category == category)
    if type:
        query = query.filter(Lead.type == type)
    if profession:
        # Filter leads that have this profession in their target_professions JSON array
        query = query.filter(Lead.target_professions.contains([profession]))
    if min_score > 0:
        query = query.filter(Lead.total_score >= min_score)
    if not include_dnc:
        query = query.filter(Lead.do_not_contact == False)
    
    # Apply sorting
    sort_column = getattr(Lead, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)
    
    # Pagination
    leads = query.offset(skip).limit(limit).all()
    
    result = []
    for lead in leads:
        result.append(LeadResponse(
            id=lead.id,
            workspace_id=lead.workspace_id,
            message_id=lead.message_id,
            type=lead.type,
            category=lead.category,
            target_professions=lead.target_professions,
            fit_score=lead.fit_score,
            money_score=lead.money_score,
            recency_score=lead.recency_score,
            confidence=lead.confidence,
            total_score=lead.total_score,
            status=lead.status,
            do_not_contact=lead.do_not_contact,
            last_contacted_at=lead.last_contacted_at,
            contact_count=lead.contact_count or 0,
            expected_revenue=lead.expected_revenue,
            lost_reason=lead.lost_reason,
            created_at=lead.created_at,
            message_text=lead.message.text if lead.message else None,
            message_author=lead.message.author if lead.message else None,
            message_date=lead.message.date if lead.message else None,
            outreach_count=len(lead.outreach_history),
            notes_count=len(lead.notes),
        ))
    
    return result


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    """Get a specific lead with full details"""
    lead = db.query(Lead).options(
        joinedload(Lead.message)
    ).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return LeadResponse(
        id=lead.id,
        workspace_id=lead.workspace_id,
        message_id=lead.message_id,
        type=lead.type,
        category=lead.category,
        fit_score=lead.fit_score,
        money_score=lead.money_score,
        recency_score=lead.recency_score,
        confidence=lead.confidence,
        total_score=lead.total_score,
        status=lead.status,
        do_not_contact=lead.do_not_contact,
        last_contacted_at=lead.last_contacted_at,
        contact_count=lead.contact_count or 0,
        expected_revenue=lead.expected_revenue,
        lost_reason=lead.lost_reason,
        created_at=lead.created_at,
        message_text=lead.message.text if lead.message else None,
        message_author=lead.message.author if lead.message else None,
        message_date=lead.message.date if lead.message else None,
        outreach_count=len(lead.outreach_history),
        notes_count=len(lead.notes),
    )


@router.get("/{lead_id}/can-contact")
def check_can_contact(lead_id: int, db: Session = Depends(get_db)):
    """Check if we can contact this lead (anti-spam check)"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    antispam = AntiSpamService(db)
    can_contact, reason = antispam.can_contact_lead(lead)
    quota = antispam.get_remaining_quota()
    
    return {
        "can_contact": can_contact,
        "reason": reason,
        "quota": quota,
    }


@router.put("/{lead_id}/status")
def update_lead_status(lead_id: int, data: LeadStatusUpdate, db: Session = Depends(get_db)):
    """Update lead CRM status"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Validate status
    valid_statuses = [s.value for s in LeadStatus]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    old_status = lead.status
    lead.status = data.status
    lead.status_changed_at = datetime.utcnow()
    
    if data.lost_reason:
        lead.lost_reason = data.lost_reason
    if data.expected_revenue is not None:
        lead.expected_revenue = data.expected_revenue
    
    # Gamification: track funnel movement
    gamification = GamificationService(db)
    
    # Award XP based on status change
    if old_status != data.status:
        gamification.increment_daily_stat("moves", 1)
        
        if data.status == "REPLIED":
            gamification.add_xp("reply_received")
        elif data.status == "CALL_SCHEDULED":
            gamification.add_xp("call_scheduled")
        elif data.status == "WON":
            gamification.add_xp("deal_won")
            # Update total revenue if provided
            if data.expected_revenue:
                progress = gamification.get_or_create_progress()
                progress.total_won += 1
                progress.total_revenue += data.expected_revenue
    
    db.commit()
    
    # Check for new badges
    new_badges = gamification.check_and_award_badges()
    
    return {
        "id": lead.id,
        "status": lead.status,
        "old_status": old_status,
        "new_badges": new_badges,
    }


@router.put("/{lead_id}/dnc")
def update_dnc_status(lead_id: int, data: LeadDNCUpdate, db: Session = Depends(get_db)):
    """Update Do Not Contact status"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    antispam = AntiSpamService(db)
    
    if data.do_not_contact:
        antispam.add_to_dnc_list(lead, data.reason or "Manually marked")
    else:
        lead.do_not_contact = False
        lead.dnc_reason = None
        db.commit()
    
    return {
        "id": lead.id,
        "do_not_contact": lead.do_not_contact,
        "dnc_reason": lead.dnc_reason,
    }


@router.get("/{lead_id}/notes")
def get_lead_notes(lead_id: int, db: Session = Depends(get_db)):
    """Get all notes for a lead"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    notes = db.query(Note).filter(Note.lead_id == lead_id).order_by(Note.created_at.desc()).all()
    
    return [{"id": n.id, "text": n.text, "created_at": n.created_at} for n in notes]


@router.post("/{lead_id}/notes")
def add_lead_note(lead_id: int, data: NoteCreate, db: Session = Depends(get_db)):
    """Add a note to a lead"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    note = Note(lead_id=lead_id, text=data.text)
    db.add(note)
    db.commit()
    db.refresh(note)
    
    return {"id": note.id, "text": note.text, "created_at": note.created_at}


@router.get("/{lead_id}/tasks")
def get_lead_tasks(lead_id: int, db: Session = Depends(get_db)):
    """Get all tasks for a lead"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    tasks = db.query(Task).filter(Task.lead_id == lead_id).order_by(Task.due_at).all()
    
    return [{
        "id": t.id,
        "type": t.type,
        "title": t.title,
        "description": t.description,
        "due_at": t.due_at,
        "status": t.status,
        "completed_at": t.completed_at,
    } for t in tasks]


@router.post("/{lead_id}/tasks")
def add_lead_task(lead_id: int, data: TaskCreate, db: Session = Depends(get_db)):
    """Add a task/reminder for a lead"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    task = Task(
        lead_id=lead_id,
        type=data.type,
        title=data.title,
        description=data.description,
        due_at=data.due_at,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {
        "id": task.id,
        "type": task.type,
        "title": task.title,
        "due_at": task.due_at,
        "status": task.status,
    }


@router.get("/stats/{workspace_id}")
def get_lead_stats(workspace_id: int, db: Session = Depends(get_db)):
    """Get lead statistics for a workspace"""
    from sqlalchemy import func
    
    # Count by status
    status_counts = db.query(
        Lead.status,
        func.count(Lead.id)
    ).filter(
        Lead.workspace_id == workspace_id
    ).group_by(Lead.status).all()
    
    # Count by category
    category_counts = db.query(
        Lead.category,
        func.count(Lead.id)
    ).filter(
        Lead.workspace_id == workspace_id
    ).group_by(Lead.category).all()
    
    # Total and averages
    totals = db.query(
        func.count(Lead.id),
        func.avg(Lead.total_score),
    ).filter(Lead.workspace_id == workspace_id).first()
    
    return {
        "total_leads": totals[0] or 0,
        "avg_score": round(float(totals[1] or 0), 2),
        "by_status": {s: c for s, c in status_counts},
        "by_category": {c: cnt for c, cnt in category_counts},
    }
