"""
Sources API routes - Telegram export management
"""
import os
import shutil
import aiofiles
import traceback
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db, SessionLocal
from app.db.models import Source, Message, Lead, Workspace, Job
from app.services.parser import TelegramParser, filter_relevant_messages
from app.services.classifier import classify_message, calculate_recency_score, calculate_total_score, quick_filter
from app.services.telegram_client import get_telegram_service
from app.services.llm import classify_message_llm

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


class JobStartResponse(BaseModel):
    job_id: int
    status: str
    message: str


class SourceLinkCreate(BaseModel):
    workspace_id: int
    title: str
    link: str


class ImportRequest(BaseModel):
    workspace_id: int
    link: str # username or invite link
    limit: int = 100
    since_date: Optional[str] = None # ISO format string
    auto_classify: bool = True # Auto-run classification after import


async def process_import_job(job_id: int, source_id: int, link: str, limit: int, since_date_str: Optional[str], auto_classify: bool = True):
    """Background task to import history from Telegram directly"""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        source = db.query(Source).filter(Source.id == source_id).first()
        
        if not job or not source:
            return

        job.status = "processing"
        job.progress = 5
        job.message = "Подключение к Telegram..."
        db.commit()

        telegram = await get_telegram_service()
        if not telegram.is_authorized:
             job.status = "failed"
             job.error = "Telegram client not authorized"
             db.commit()
             db.delete(source)
             db.commit()
             return

        # Parse date if provided
        offset_date = None
        if since_date_str:
            try:
                offset_date = datetime.fromisoformat(since_date_str.replace('Z', '+00:00'))
            except:
                pass
        
        job.message = f"Получение истории (лимит: {limit})..."
        job.total_items = limit
        db.commit()

        # Execute Import
        try:
            processed = 0
            # Consuming stream
            async for result in telegram.import_history_stream(link, limit=limit, offset_date=offset_date, batch_size=50):
                if result.get("status") == "error":
                    print(f"Import stream error: {result.get('message')}")
                    # We continue or break? Let's log and continue if possible, or break if critical
                    # Usually error here means disconnection or heavy failure
                    raise Exception(result.get("message"))
                
                messages_data = result.get("messages", [])
                
                # Update source details on first batch
                if result.get("chat_title") and not source.title.startswith("Import:"):
                   # Only update if we don't have a good title yet, or overwrite?
                   pass
                if result.get("chat_title"):
                     source.title = result.get("chat_title")
                
                source.type = "telegram_import"

                for msg_data in messages_data:
                    message = Message(
                        source_id=source.id,
                        msg_id=str(msg_data.get('id')), 
                        date=datetime.fromisoformat(msg_data.get('date')),
                        author=msg_data.get('sender_name'),
                        author_id=str(msg_data.get('sender_id')) if msg_data.get('sender_id') else None,
                        text=msg_data.get('text'),
                        raw_json=msg_data.get('raw_json'),
                    )
                    db.add(message)
                
                processed += len(messages_data)
                
                # Update Job Progress
                # Progress ranges from 10% to 90% during download
                job.processed_items = processed
                progress_percent = 10 + int((processed / limit) * 80)
                job.progress = min(progress_percent, 90) # Cap at 90 until done
                job.message = f"Загружено {processed} сообщений..."
                
                db.commit()
                # Clear session identity map to prevent memory bloat on large imports
                db.expunge_all() 
                
                # Re-fetch objects attached to session if needed (job, source)
                # But we modified them, so they might be detached.
                # Actually, simple db.commit() expires them, so next access reloads them.
                # Since we access them in next loop iteration (job.progress = ...), they will be re-fetched.
                # Just need to make sure they exist.
                # Performance optimization: we could just update the ID without fetching, but ORM is cleaner.
                
                # We need to re-fetch/merge job and source because expunge_all detached them
                job = db.merge(job)
                source = db.merge(source)

            source.parsed_at = datetime.utcnow()
            source.message_count = processed
            
            job.status = "completed"
            job.progress = 100
            job.total_items = processed # Update total to actual matched
            job.message = f"Импорт завершен: {processed} сообщений"
            job.result = {"source_id": source.id, "message_count": processed, "auto_classify": auto_classify}
            
            db.commit()
            
            # Auto-classify if requested
            if auto_classify and processed > 0:
                job.message = "Импорт завершен. Запуск классификации..."
                db.commit()
                # Trigger classification inline
                # Note: process_classify_job_inline uses its own queries, so it's fine.
                process_classify_job_inline(source.id, db)

        except Exception as e:
            job.status = "failed"
            job.error = f"Import error: {str(e)}"
            db.delete(source) # Cleanup
            db.commit()
            
    except Exception as e:
        print(f"Import Job Failed: {e}")
        try:
            job.status = "failed"
            job.error = str(e)
            db.commit()
        except:
            pass
    finally:
        db.close()


def process_upload_job(job_id: int, file_path: str, source_id: int):
    """Background task to parse uploaded file"""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        source = db.query(Source).filter(Source.id == source_id).first()
        
        if not job or not source:
            return

        job.status = "processing"
        job.progress = 10
        db.commit()

        # Parse file
        try:
            result = TelegramParser.parse(file_path)
            messages_data = result['messages']
            total_msgs = len(messages_data)
            
            job.total_items = total_msgs
            db.commit()

            # Save messages in batches
            batch_size = 100
            processed = 0
            
            for i in range(0, total_msgs, batch_size):
                batch = messages_data[i:i+batch_size]
                
                for msg_data in batch:
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
                
                processed += len(batch)
                job.processed_items = processed
                job.progress = 10 + int((processed / total_msgs) * 90)
                db.commit()
            
            source.parsed_at = datetime.utcnow()
            source.message_count = total_msgs
            
            job.status = "completed"
            job.progress = 100
            job.result = {"source_id": source.id, "message_count": total_msgs}
            
            db.commit()
            
        except Exception as e:
            job.status = "failed"
            job.error = f"Parse error: {str(e)}"
            # Cleanup source on failure
            db.delete(source)
            db.commit()
            if os.path.exists(file_path):
                os.remove(file_path)
                
    except Exception as e:
        print(f"Job failed: {e}")
        # Last resort error update
        try:
            job.status = "failed"
            job.error = str(e)
            db.commit()
        except:
            pass
    finally:
        db.close()


def process_classify_job_inline(source_id: int, db: Session):
    """Inline classification (uses existing db session)"""
    import hashlib
    import re
    
    # NON-TECH ROLES FILTER - these are NOT tech tasks for automation specialist
    NON_TECH_ROLES_RE = re.compile(
        r"(?i)\b(продаж\w*|менеджер\w*|менедж\w*|оператор\w*|"
        r"администратор\w*|секретар\w*|бухгалтер\w*|hr\w*|"
        r"smm|смм|таргетолог\w*|дизайн\w*|копирайт\w*|"
        r"рилсмейкер\w*|монтаж\w*|репетитор\w*|учител\w*|"
        r"продавец\w*|логист\w*|закупщ\w*|консультант\w*)\b"
    )
    
    # Get all message IDs for this source
    message_ids = db.query(Message.id).filter(Message.source_id == source_id).all()
    message_ids = [m[0] for m in message_ids]
    
    if not message_ids:
        return
    
    # Get existing lead message_ids for this source efficiently
    # Avoid passing huge list of IDs to IN clause (causes "too many SQL variables")
    existing_leads = db.query(Lead.message_id).join(Message, Lead.message_id == Message.id).filter(Message.source_id == source_id).all()
    existing_ids = set(l[0] for l in existing_leads)
    
    # ANTI-DUPLICATE: Get text hashes of existing leads to detect duplicates by content
    existing_text_hashes = set()
    for lead_id in existing_ids:
        msg = db.query(Message.text).filter(Message.id == lead_id).first()
        if msg and msg.text:
            text_hash = hashlib.md5(msg.text.strip().lower()[:200].encode()).hexdigest()
            existing_text_hashes.add(text_hash)
    
    # Determine messages to process
    to_process_ids = [mid for mid in message_ids if mid not in existing_ids]
    
    if not to_process_ids:
        return
    
    # Get workspace_id from source
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        return
    workspace_id = source.workspace_id
    
    leads_created = 0
    
    # Process in chunks
    chunk_size = 50
    
    for i in range(0, len(to_process_ids), chunk_size):
        chunk_ids = to_process_ids[i:i+chunk_size]
        messages = db.query(Message).filter(Message.id.in_(chunk_ids)).all()
        
        for message in messages:
            text = message.text or ""
            
            # Skip very short messages
            if len(text) < 15:
                continue
            
            # ANTI-DUPLICATE: Check if similar text already exists
            text_hash = hashlib.md5(text.strip().lower()[:200].encode()).hexdigest()
            if text_hash in existing_text_hashes:
                continue  # Skip duplicate content
            
            text_lower = text.lower()
            
            # =========== STRICT PRE-FILTERS ===========
            # Filter 1: EXPLICIT #помогу / offer rejection
            if re.search(r'(?i)(#помогу|#предлагаю|помогу\s+с\s+|возьму\s+проект|беру\s+заказ)', text_lower):
                continue  # This is someone offering services, not a task
            
            # Filter 2: Job seeker posts (people looking for work)
            if re.search(r'(?i)(ищу\s+работу|в\s+поиске\s+работы|ищу\s+заказы|ищу\s+подработку|открыт\s+для\s+предложений)', text_lower):
                continue  # Not a client task
            
            # Filter 3: NON-TECH ROLES - be VERY strict
            if NON_TECH_ROLES_RE.search(text):
                # Double-check: if it also has tech keywords, it might be valid
                tech_keywords = ['бот', 'автоматизац', 'парсинг', 'интеграц', 'api', 'n8n', 'make', 'python', 'скрипт', 'gpt', 'нейросет', 'ии']
                has_tech = any(kw in text_lower for kw in tech_keywords)
                if not has_tech:
                    continue  # Pure non-tech role, skip
            
            # Filter 4: Quick filter for obvious non-leads
            is_potential, quick_type = quick_filter(text)
            if not is_potential:
                continue
            
            # =========== LLM VALIDATION FOR ALL CANDIDATES ===========
            # Run LLM on EVERY candidate to confirm it's a real tech task
            try:
                llm_result = classify_message_llm(text)
                
                # BE STRICT: Only accept if LLM confirms it's a tech task with confidence
                if not llm_result.get('is_tech_task', False):
                    continue  # LLM says it's not a tech task
                
                if llm_result.get('confidence', 0) < 0.5:
                    continue  # Low confidence, skip
                
            except Exception as e:
                # If LLM fails, be conservative and skip
                print(f"LLM error, skipping message: {e}")
                continue
            
            # =========== SAVE CONFIRMED TECH LEAD ===========
            # Only get here if LLM confirmed this is a tech task
            classification = classify_message(text, message.author or "")
            
            recency_score = calculate_recency_score(message.date)
            total_score = calculate_total_score(
                classification['fit_score'],
                classification['money_score'],
                recency_score,
                llm_result.get('confidence', 0.7)  # Use LLM confidence
            )
            
            lead = Lead(
                workspace_id=workspace_id,
                message_id=message.id,
                type='TASK',  # Always TASK since LLM confirmed
                category=llm_result.get('task_type', 'Other').capitalize(),
                target_professions=classification.get('target_professions'),
                fit_score=classification['fit_score'],
                money_score=classification['money_score'],
                recency_score=recency_score,
                confidence=llm_result.get('confidence', 0.7),
                total_score=total_score,
                status="NEW",
            )
            
            db.add(lead)
            leads_created += 1
            
            # Track this hash to prevent duplicates in same batch
            existing_text_hashes.add(text_hash)
        
        db.commit()
    
    print(f"Auto-classified source {source_id}: {leads_created} leads created")


def process_classify_job(job_id: int, source_id: int, use_llm: bool):
    """Background task to classify messages"""
    print(f"DEBUG: Starting classify job {job_id} for source {source_id}")
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            print(f"DEBUG: Job {job_id} not found")
            return

        job.status = "processing"
        job.progress = 5
        job.message = "Загрузка сообщений..."
        db.commit()
        print(f"DEBUG: Job {job_id} status set to processing")
        
        # Get all message IDs for this source
        message_ids = db.query(Message.id).filter(Message.source_id == source_id).all()
        message_ids = [m[0] for m in message_ids]
        
        # Get existing lead message_ids efficienty
        existing_leads = db.query(Lead.message_id).join(Message, Lead.message_id == Message.id).filter(Message.source_id == source_id).all()
        existing_ids = set(l[0] for l in existing_leads)
        existing_ids = set(l[0] for l in existing_leads)
        
        # Determine messages to process
        to_process_ids = [mid for mid in message_ids if mid not in existing_ids]
        
        job.total_items = len(to_process_ids)
        db.commit()
        
        if len(to_process_ids) == 0:
            job.status = "completed"
            job.progress = 100
            job.result = {"classified": 0, "leads_created": 0}
            db.commit()
            return

        processed_count = 0
        leads_created = 0
        
        # Process in chunks
        chunk_size = 50
        
        for i in range(0, len(to_process_ids), chunk_size):
            chunk_ids = to_process_ids[i:i+chunk_size]
            messages = db.query(Message).filter(Message.id.in_(chunk_ids)).all()
            
            for message in messages:
                text = message.text or ""
                
                # Classification Logic
                is_potential, quick_type = quick_filter(text)
                
                classification = None
                if not is_potential:
                    # Skip or mark as chatter? We just skip creating lead
                    pass
                else:
                    if use_llm:
                        try:
                            classification = classify_message(text, message.author or "")
                        except:
                            # Fallback
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
                
                if classification and classification['type'] in ['TASK', 'VACANCY']:
                    recency_score = calculate_recency_score(message.date)
                    total_score = calculate_total_score(
                        classification['fit_score'],
                        classification['money_score'],
                        recency_score,
                        classification['confidence']
                    )
                    
                    lead = Lead(
                        workspace_id=source_id, # Actually need to lookup workspace_id from source, but simplified
                        message_id=message.id,
                        type=classification['type'],
                        category=classification.get('category', 'Other'),
                        target_professions=classification.get('target_professions'),
                        fit_score=classification['fit_score'],
                        money_score=classification['money_score'],
                        recency_score=recency_score,
                        confidence=classification['confidence'],
                        total_score=total_score,
                        status="NEW",
                    )
                    
                    # Need to get workspace_id
                    # This is slightly inefficient, better to fetch source once
                    src = db.query(Source).filter(Source.id == source_id).first()
                    lead.workspace_id = src.workspace_id
                    
                    db.add(lead)
                    leads_created += 1
                
                processed_count += 1
            
            # Update progress
            db.commit()
            job.processed_items = processed_count
            job.progress = int((processed_count / job.total_items) * 100)
            db.commit()

        job.status = "completed"
        job.progress = 100
        job.result = {"classified": processed_count, "leads_created": leads_created}
        db.commit()

    except Exception as e:
        print(f"DEBUG: Classification job {job_id} failed: {e}")
        traceback.print_exc()
        try:
            job.status = "failed"
            job.error = str(e)
            job.result = {"traceback": traceback.format_exc()}
            db.commit()
        except:
            pass
    finally:
        db.close()
        print(f"DEBUG: Classification job {job_id} finished")


@router.get("/workspace/{workspace_id}", response_model=List[SourceResponse])
def list_sources(workspace_id: int, db: Session = Depends(get_db)):
    """List all sources for a workspace"""
    sources = db.query(Source).filter(Source.workspace_id == workspace_id).all()
    return sources


@router.post("/link", response_model=JobStartResponse, status_code=status.HTTP_201_CREATED)
async def import_from_link(
    data: ImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Import messages from a Telegram link (username or invite)"""
    workspace = db.query(Workspace).filter(Workspace.id == data.workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Create source placeholder
    source = Source(
        workspace_id=data.workspace_id,
        type="telegram_import_pending",
        title=f"Import: {data.link}",
        link=data.link,
        message_count=0
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    
    # Create Job
    job = Job(
        type="import_history",
        status="pending",
        total_items=data.limit,
        processed_items=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Start background task
    background_tasks.add_task(
        process_import_job, 
        job.id, 
        source.id, 
        data.link, 
        data.limit, 
        data.since_date,
        data.auto_classify
    )
    
    return {
        "job_id": job.id,
        "status": "pending",
        "message": "Import job started"
    }


@router.post("/upload", response_model=JobStartResponse, status_code=status.HTTP_201_CREATED)
async def upload_telegram_export(
    background_tasks: BackgroundTasks,
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
    
    file_type = "telegram_json" if filename.endswith('.json') else "telegram_html"
    
    # Create source record (empty initially)
    source = Source(
        workspace_id=workspace_id,
        type=file_type,
        title=title,
        file_path=file_path,
        message_count=0
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    
    # Create Job
    job = Job(
        type="upload_source",
        status="pending",
        total_items=0,
        processed_items=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Start background task
    background_tasks.add_task(process_upload_job, job.id, file_path, source.id)
    
    return {
        "job_id": job.id,
        "status": "pending",
        "message": "File uploaded, parsing started"
    }


@router.post("/{source_id}/classify", response_model=JobStartResponse)
def classify_source_messages(
    source_id: int, 
    background_tasks: BackgroundTasks,
    use_llm: bool = True,
    db: Session = Depends(get_db)
):
    """Classify all messages from a source and create leads"""
    print(f"DEBUG: classify_source_messages called for source {source_id}")
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Create Job
    job = Job(
        type="classify_source",
        status="pending",
        total_items=0,
        processed_items=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Start background task using threading (BackgroundTasks was not executing)
    import threading
    thread = threading.Thread(target=process_classify_job, args=(job.id, source_id, use_llm))
    thread.start()
    
    return {
        "job_id": job.id,
        "status": "pending",
        "message": "Classification started"
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
