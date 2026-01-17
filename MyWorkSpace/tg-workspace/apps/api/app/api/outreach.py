"""
Outreach API routes - Message drafts and sending tracking
"""
from typing import List, Optional
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Outreach, Lead, Template
from app.services.antispam import AntiSpamService
from app.services.gamification import GamificationService
from app.services.llm import generate_outreach_message, uniqualize_message

router = APIRouter()


class OutreachCreate(BaseModel):
    lead_id: int
    message_text: str
    template_id: Optional[int] = None


class OutreachResponse(BaseModel):
    id: int
    lead_id: int
    message_text: str
    template_id: Optional[int]
    created_at: datetime
    sent_at: Optional[datetime]
    result_status: Optional[str]
    replied_at: Optional[datetime]

    class Config:
        from_attributes = True


class GenerateMessageRequest(BaseModel):
    lead_id: int
    template_id: Optional[int] = None
    custom_context: Optional[str] = None


@router.get("/lead/{lead_id}", response_model=List[OutreachResponse])
def list_outreach_history(lead_id: int, db: Session = Depends(get_db)):
    """Get outreach history for a lead"""
    outreach = db.query(Outreach).filter(
        Outreach.lead_id == lead_id
    ).order_by(Outreach.created_at.desc()).all()
    
    return outreach


@router.post("/draft", response_model=OutreachResponse)
def create_outreach_draft(data: OutreachCreate, db: Session = Depends(get_db)):
    """Create an outreach message draft (not sent yet)"""
    lead = db.query(Lead).filter(Lead.id == data.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check uniqueness
    antispam = AntiSpamService(db)
    is_unique, message = antispam.check_message_uniqueness(data.lead_id, data.message_text)
    
    if not is_unique:
        raise HTTPException(status_code=400, detail=message)
    
    outreach = Outreach(
        lead_id=data.lead_id,
        message_text=data.message_text,
        template_id=data.template_id,
    )
    db.add(outreach)
    db.commit()
    db.refresh(outreach)
    
    return outreach


@router.post("/generate")
def generate_message(data: GenerateMessageRequest, db: Session = Depends(get_db)):
    """Generate a personalized outreach message using AI"""
    lead = db.query(Lead).filter(Lead.id == data.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Get message text
    lead_text = lead.message.text if lead.message else ""
    lead_author = lead.message.author if lead.message else ""
    
    # Get template if specified
    template_text = None
    if data.template_id:
        template = db.query(Template).filter(Template.id == data.template_id).first()
        if template:
            template_text = template.text
    
    # Get previous outreach for context
    previous = db.query(Outreach).filter(
        Outreach.lead_id == data.lead_id,
        Outreach.sent_at != None
    ).order_by(Outreach.sent_at.desc()).limit(3).all()
    
    previous_messages = [o.message_text for o in previous]
    
    # Generate
    result = generate_outreach_message(
        lead_text=lead_text,
        lead_author=lead_author,
        category=lead.category,
        template=template_text,
        previous_messages=previous_messages if previous_messages else None,
        context={
            "contact_count": lead.contact_count or 0,
            "money_score": lead.money_score,
        }
    )
    
    return {
        "generated_message": result.get("message", ""),
        "hook": result.get("hook", ""),
        "next_step": result.get("next_step", ""),
        "personalization_points": result.get("personalization_points", []),
        "model_used": result.get("model_used", ""),
    }


@router.post("/uniqualize")
def uniqualize_template(template_text: str, variations: int = 3, db: Session = Depends(get_db)):
    """Generate unique variations of a message template"""
    result = uniqualize_message(template_text, variations)
    return {"variations": result}


@router.post("/{outreach_id}/mark-sent")
def mark_as_sent(outreach_id: int, db: Session = Depends(get_db)):
    """Mark an outreach message as sent (user confirmed they sent it)"""
    outreach = db.query(Outreach).filter(Outreach.id == outreach_id).first()
    if not outreach:
        raise HTTPException(status_code=404, detail="Outreach not found")
    
    if outreach.sent_at:
        raise HTTPException(status_code=400, detail="Already marked as sent")
    
    lead = db.query(Lead).filter(Lead.id == outreach.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check anti-spam
    antispam = AntiSpamService(db)
    can_contact, reason = antispam.can_contact_lead(lead)
    
    if not can_contact:
        raise HTTPException(status_code=400, detail=reason)
    
    # Record the send
    antispam.record_outreach_sent(lead, outreach)
    
    # Update lead status if NEW
    if lead.status == "NEW":
        lead.status = "CONTACTED"
        lead.status_changed_at = datetime.utcnow()
    
    # Gamification
    gamification = GamificationService(db)
    is_followup = (lead.contact_count or 0) > 1
    
    if is_followup:
        xp_result = gamification.add_xp("followup_sent")
    else:
        xp_result = gamification.add_xp("outreach_sent")
        gamification.increment_daily_stat("messages", 1)
    
    # Update template usage
    if outreach.template_id:
        template = db.query(Template).filter(Template.id == outreach.template_id).first()
        if template:
            template.usage_count = (template.usage_count or 0) + 1
    
    db.commit()
    
    # Check badges
    new_badges = gamification.check_and_award_badges()
    
    return {
        "id": outreach.id,
        "sent_at": outreach.sent_at,
        "xp_earned": xp_result.get("xp_earned", 0),
        "new_badges": new_badges,
        "quota": antispam.get_remaining_quota(),
    }


@router.post("/{outreach_id}/mark-replied")
def mark_as_replied(outreach_id: int, db: Session = Depends(get_db)):
    """Mark that the contact replied to this outreach"""
    outreach = db.query(Outreach).filter(Outreach.id == outreach_id).first()
    if not outreach:
        raise HTTPException(status_code=404, detail="Outreach not found")
    
    outreach.result_status = "replied"
    outreach.replied_at = datetime.utcnow()
    
    # Update lead status
    lead = db.query(Lead).filter(Lead.id == outreach.lead_id).first()
    if lead and lead.status == "CONTACTED":
        lead.status = "REPLIED"
        lead.status_changed_at = datetime.utcnow()
    
    # Gamification
    gamification = GamificationService(db)
    xp_result = gamification.add_xp("reply_received")
    
    db.commit()
    
    new_badges = gamification.check_and_award_badges()
    
    return {
        "id": outreach.id,
        "result_status": outreach.result_status,
        "xp_earned": xp_result.get("xp_earned", 0),
        "new_badges": new_badges,
    }


@router.get("/stats/today")
def get_today_stats(db: Session = Depends(get_db)):
    """Get today's outreach statistics"""
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    sent_today = db.query(Outreach).filter(
        Outreach.sent_at >= today_start
    ).count()
    
    replied_today = db.query(Outreach).filter(
        Outreach.replied_at >= today_start
    ).count()
    
    antispam = AntiSpamService(db)
    quota = antispam.get_remaining_quota()
    risk = antispam.get_risk_assessment()
    
    return {
        "sent_today": sent_today,
        "replied_today": replied_today,
        "quota": quota,
        "risk_assessment": risk,
    }


@router.get("/pending-followups")
def get_pending_followups(
    workspace_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get leads that need follow-up today"""
    from app.db.models import Task
    
    now = datetime.utcnow()
    
    # Get tasks due today or overdue
    tasks = db.query(Task).join(Lead).filter(
        Lead.workspace_id == workspace_id,
        Task.status == "pending",
        Task.due_at <= now + timedelta(days=1),  # Due within 24h
    ).order_by(Task.due_at).limit(limit).all()
    
    result = []
    for task in tasks:
        lead = task.lead
        result.append({
            "task_id": task.id,
            "task_type": task.type,
            "task_title": task.title,
            "due_at": task.due_at,
            "lead_id": lead.id,
            "lead_author": lead.message.author if lead.message else None,
            "lead_status": lead.status,
            "is_overdue": task.due_at < now,
        })
    
    return result
