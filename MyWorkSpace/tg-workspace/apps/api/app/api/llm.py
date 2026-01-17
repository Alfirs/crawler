"""
LLM API routes for AI features
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Lead
from app.services.llm import get_sales_coach_advice, handle_objection, test_connection

router = APIRouter()


class CoachRequest(BaseModel):
    lead_id: int


class ObjectionRequest(BaseModel):
    lead_id: int
    objection_text: str


@router.post("/coach")
def get_coach_advice(data: CoachRequest, db: Session = Depends(get_db)):
    """Get AI sales coach advice for a lead"""
    lead = db.query(Lead).filter(Lead.id == data.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    lead_info = {
        "type": lead.type,
        "category": lead.category,
        "text": lead.message.text if lead.message else "",
        "author": lead.message.author if lead.message else "",
        "fit_score": lead.fit_score,
        "money_score": lead.money_score,
        "contact_count": lead.contact_count or 0,
    }
    
    advice = get_sales_coach_advice(
        lead_info=lead_info,
        current_status=lead.status,
    )
    
    return advice


@router.post("/objection")
def handle_objection_request(data: ObjectionRequest, db: Session = Depends(get_db)):
    """Get help with handling an objection"""
    lead = db.query(Lead).filter(Lead.id == data.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    context = f"Lead: {lead.message.text if lead.message else ''}"
    
    response = handle_objection(
        objection_text=data.objection_text,
        lead_context=context,
    )
    
    return response


@router.get("/test")
def test_gemini_connection():
    """Test Gemini API connection"""
    return test_connection()
