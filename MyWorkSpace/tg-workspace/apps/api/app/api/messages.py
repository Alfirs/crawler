"""
Messages API routes
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Message, Source

router = APIRouter()


class MessageResponse(BaseModel):
    id: int
    source_id: int
    msg_id: Optional[str]
    date: Optional[datetime]
    author: Optional[str]
    author_id: Optional[str]
    text: Optional[str]
    created_at: datetime
    has_lead: bool = False

    class Config:
        from_attributes = True


@router.get("/source/{source_id}", response_model=List[MessageResponse])
def list_messages(
    source_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """List messages from a source with pagination"""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    messages = db.query(Message).filter(
        Message.source_id == source_id
    ).order_by(Message.date.desc()).offset(skip).limit(limit).all()
    
    result = []
    for msg in messages:
        result.append(MessageResponse(
            id=msg.id,
            source_id=msg.source_id,
            msg_id=msg.msg_id,
            date=msg.date,
            author=msg.author,
            author_id=msg.author_id,
            text=msg.text,
            created_at=msg.created_at,
            has_lead=msg.lead is not None,
        ))
    
    return result


@router.get("/{message_id}", response_model=MessageResponse)
def get_message(message_id: int, db: Session = Depends(get_db)):
    """Get a specific message"""
    message = db.query(Message).filter(Message.id == message_id).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return MessageResponse(
        id=message.id,
        source_id=message.source_id,
        msg_id=message.msg_id,
        date=message.date,
        author=message.author,
        author_id=message.author_id,
        text=message.text,
        created_at=message.created_at,
        has_lead=message.lead is not None,
    )


@router.get("/search/", response_model=List[MessageResponse])
def search_messages(
    source_id: int,
    query: str = Query(..., min_length=2),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Search messages by text content"""
    messages = db.query(Message).filter(
        Message.source_id == source_id,
        Message.text.ilike(f"%{query}%")
    ).limit(limit).all()
    
    result = []
    for msg in messages:
        result.append(MessageResponse(
            id=msg.id,
            source_id=msg.source_id,
            msg_id=msg.msg_id,
            date=msg.date,
            author=msg.author,
            author_id=msg.author_id,
            text=msg.text,
            created_at=msg.created_at,
            has_lead=msg.lead is not None,
        ))
    
    return result
