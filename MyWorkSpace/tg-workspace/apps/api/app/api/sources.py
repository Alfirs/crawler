"""
Sources API routes - Telegram export management
"""
import os
import shutil
import aiofiles
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Source, Message, Lead, Workspace
from app.services.parser import TelegramParser, filter_relevant_messages
from app.services.classifier import classify_message, calculate_recency_score, calculate_total_score, quick_filter

router = APIRouter()

# Upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class SourceResponse(BaseModel):
    id: int
    workspace_id: int
    type: str
    title: str
    link: Optional[str]
    file_path: Optional[str]
    created_at: datetime
    parsed_at: Optional[datetime]
    message_count: int

    class Config:
        from_attributes = True


class SourceLinkCreate(BaseModel):
    workspace_id: int
    title: str
    link: str


@router.get("/workspace/{workspace_id}", response_model=List[SourceResponse])
def list_sources(workspace_id: int, db: Session = Depends(get_db)):
    """List all sources for a workspace"""
    sources = db.query(Source).filter(Source.workspace_id == workspace_id).all()
    return sources


@router.post("/link", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def add_link_source(data: SourceLinkCreate, db: Session = Depends(get_db)):
    """Add a Telegram link as source (for reference only, no parsing)"""
    # Verify workspace exists
    workspace = db.query(Workspace).filter(Workspace.id == data.workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    source = Source(
        workspace_id=data.workspace_id,
        type="link",
        title=data.title,
        link=data.link,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    
    return source


@router.post("/upload", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_telegram_export(
    workspace_id: int = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and parse a Telegram export file (JSON or HTML)"""
    # Verify workspace exists
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Validate file type
    filename = file.filename.lower()
    if not (filename.endswith('.json') or filename.endswith('.html') or filename.endswith('.htm')):
        raise HTTPException(status_code=400, detail="Only JSON and HTML files are supported")
    
    # Save file
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{workspace_id}_{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Determine file type
    file_type = "telegram_json" if filename.endswith('.json') else "telegram_html"
    
    # Create source record
    source = Source(
        workspace_id=workspace_id,
        type=file_type,
        title=title,
        file_path=file_path,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    
    # Parse the file
    try:
        result = TelegramParser.parse(file_path)
        messages = result['messages']
        
        # Save messages to database
        for msg_data in messages:
            message = Message(
                source_id=source.id,
                msg_id=msg_data.get('msg_id'),
                date=msg_data.get('date'),
                author=msg_data.get('author'),
                author_id=msg_data.get('author_id'),
                text=msg_data.get('text'),
                raw_json=msg_data.get('raw_json'),
            )
            db.add(message)
        
        source.parsed_at = datetime.utcnow()
        source.message_count = len(messages)
        db.commit()
        
    except Exception as e:
        # Rollback and delete source if parsing fails
        db.delete(source)
        db.commit()
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
    
    db.refresh(source)
    return source


@router.post("/{source_id}/classify")
def classify_source_messages(
    source_id: int, 
    use_llm: bool = True,
    db: Session = Depends(get_db)
):
    """Classify all messages from a source and create leads"""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Get unclassified messages (those without leads)
    messages = db.query(Message).filter(
        Message.source_id == source_id
    ).all()
    
    classified_count = 0
    leads_created = 0
    
    for message in messages:
        # Check if lead already exists
        existing_lead = db.query(Lead).filter(Lead.message_id == message.id).first()
        if existing_lead:
            continue
        
        text = message.text or ""
        
        # Quick filter first
        is_potential, quick_type = quick_filter(text)
        
        if not is_potential:
            # Skip non-potential messages
            continue
        
        # Classify with LLM if enabled
        if use_llm:
            try:
                classification = classify_message(text, message.author or "")
            except Exception as e:
                # Fallback to quick classification
                classification = {
                    "type": quick_type,
                    "category": "Other",
                    "fit_score": 0.5,
                    "money_score": 0.5,
                    "confidence": 0.3,
                }
        else:
            classification = {
                "type": quick_type,
                "category": "Other",
                "fit_score": 0.5,
                "money_score": 0.5,
                "confidence": 0.5,
            }
        
        # Calculate recency
        recency_score = calculate_recency_score(message.date)
        
        # Calculate total score
        total_score = calculate_total_score(
            classification['fit_score'],
            classification['money_score'],
            recency_score,
            classification['confidence']
        )
        
        # Only create leads for TASK or VACANCY types
        if classification['type'] in ['TASK', 'VACANCY']:
            lead = Lead(
                workspace_id=source.workspace_id,
                message_id=message.id,
                type=classification['type'],
                category=classification.get('category', 'Other'),
                fit_score=classification['fit_score'],
                money_score=classification['money_score'],
                recency_score=recency_score,
                confidence=classification['confidence'],
                total_score=total_score,
                status="NEW",
            )
            db.add(lead)
            leads_created += 1
        
        classified_count += 1
    
    db.commit()
    
    return {
        "source_id": source_id,
        "messages_processed": classified_count,
        "leads_created": leads_created,
    }


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    """Delete a source and its messages"""
    source = db.query(Source).filter(Source.id == source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Delete file if exists
    if source.file_path and os.path.exists(source.file_path):
        os.remove(source.file_path)
    
    db.delete(source)
    db.commit()
