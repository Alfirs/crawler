"""
Telegram API routes for live integration
"""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.telegram_client import telegram_service, TelegramService

router = APIRouter()


class InitRequest(BaseModel):
    api_id: int
    api_hash: str


class PhoneRequest(BaseModel):
    phone: str


class CodeRequest(BaseModel):
    code: str


class PasswordRequest(BaseModel):
    password: str


class SendMessageRequest(BaseModel):
    chat_id: int
    text: str
    reply_to: Optional[int] = None


class MonitorRequest(BaseModel):
    chat_ids: list[int]


# Initialization and Auth

@router.post("/init")
async def initialize_client(data: InitRequest):
    """Initialize Telegram client with API credentials"""
    try:
        result = await telegram_service.initialize(data.api_id, data.api_hash)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/start")
async def start_auth(data: PhoneRequest):
    """Start phone authentication"""
    if not telegram_service.client:
        raise HTTPException(
            status_code=400, 
            detail="Client not initialized. Call /init first."
        )
    
    result = await telegram_service.start_auth(data.phone)
    return result


@router.get("/auth/qr")
async def start_qr_auth():
    """Start QR code authentication"""
    if not telegram_service.client:
        raise HTTPException(
            status_code=400, 
            detail="Client not initialized. Call /init first with any data."
        )
    
    result = await telegram_service.start_qr_auth()
    return result


@router.get("/auth/qr/check")
async def check_qr_auth():
    """Check QR auth status"""
    result = await telegram_service.check_qr_auth()
    return result


@router.post("/auth/code")
async def verify_code(data: CodeRequest):
    """Verify phone code"""
    if not telegram_service.client:
        raise HTTPException(status_code=400, detail="Client not initialized")
    
    result = await telegram_service.verify_code(data.code)
    return result


@router.post("/auth/2fa")
async def verify_2fa(data: PasswordRequest):
    """Verify 2FA password"""
    if not telegram_service.client:
        raise HTTPException(status_code=400, detail="Client not initialized")
    
    result = await telegram_service.verify_2fa(data.password)
    return result


@router.get("/auth/status")
async def get_auth_status():
    """Get current authorization status"""
    result = await telegram_service.get_auth_status()
    return result


@router.post("/auth/logout")
async def logout():
    """Logout and clear session"""
    result = await telegram_service.logout()
    return result


# Dialogs and Messages

@router.get("/dialogs")
async def get_dialogs(limit: int = 100):
    """Get list of dialogs (chats)"""
    if not telegram_service.is_authorized:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        dialogs = await telegram_service.get_dialogs(limit=limit)
        return {"dialogs": dialogs, "count": len(dialogs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages/{chat_id}")
async def get_messages(chat_id: int, limit: int = 50, offset_id: int = 0):
    """Get messages from a chat"""
    if not telegram_service.is_authorized:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        messages = await telegram_service.get_messages(
            chat_id, 
            limit=limit,
            offset_id=offset_id
        )
        return {"messages": messages, "count": len(messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send")
async def send_message(data: SendMessageRequest):
    """Send a message to a chat"""
    if not telegram_service.is_authorized:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    result = await telegram_service.send_message(
        data.chat_id,
        data.text,
        reply_to=data.reply_to
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    
    return result


@router.get("/entity/{identifier}")
async def get_entity(identifier: str):
    """Get info about a user/chat by username or ID"""
    if not telegram_service.is_authorized:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    # Try to parse as int (ID), otherwise treat as username
    try:
        entity_id = int(identifier)
    except ValueError:
        entity_id = identifier
    
    result = await telegram_service.get_entity_info(entity_id)
    return result


# Monitoring (for future WebSocket implementation)

@router.post("/monitor/start")
async def start_monitoring(data: MonitorRequest, background_tasks: BackgroundTasks):
    """Start monitoring chats for new messages"""
    if not telegram_service.is_authorized:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    # For now, just return status
    # Real implementation would use WebSockets
    return {
        "status": "monitoring_started",
        "chat_ids": data.chat_ids,
        "message": "Мониторинг запущен. Новые сообщения будут сохраняться автоматически."
    }


@router.post("/monitor/stop")
async def stop_monitoring():
    """Stop monitoring"""
    return {"status": "monitoring_stopped"}


# Quick import from chat

@router.post("/import/{chat_id}")
async def import_from_chat(
    chat_id: int, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Import messages from a Telegram chat directly"""
    if not telegram_service.is_authorized:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    from app.db.models import Source, Message, Workspace
    from datetime import datetime
    
    # Get messages
    messages = await telegram_service.get_messages(chat_id, limit=limit)
    
    if not messages:
        return {"imported": 0, "message": "No messages found"}
    
    # Get or create default workspace
    workspace = db.query(Workspace).first()
    if not workspace:
        workspace = Workspace(name="Telegram Import")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
    
    # Create source
    source = Source(
        workspace_id=workspace.id,
        type="telegram_live",
        title=f"Chat {chat_id}",
        parsed_at=datetime.utcnow(),
        message_count=len(messages)
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    
    # Save messages
    for msg in messages:
        db_message = Message(
            source_id=source.id,
            msg_id=str(msg["id"]),
            date=datetime.fromisoformat(msg["date"]) if msg.get("date") else None,
            author=msg.get("sender_name"),
            author_id=str(msg.get("sender_id")) if msg.get("sender_id") else None,
            text=msg.get("text")
        )
        db.add(db_message)
    
    db.commit()
    
    return {
        "imported": len(messages),
        "source_id": source.id,
        "workspace_id": workspace.id,
        "message": f"Импортировано {len(messages)} сообщений"
    }
