"""
Autopost API routes
"""
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.services.autopost import autopost_service
from app.services.telegram_client import telegram_service

router = APIRouter()


class UpdateConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    message_text: Optional[str] = None
    chat_ids: Optional[List[int]] = None
    chat_names: Optional[Dict[int, str]] = None
    schedule_time: Optional[str] = None
    interval_seconds: Optional[int] = None
    randomize_order: Optional[bool] = None
    text_variations: Optional[List[str]] = None
    ai_rewrite: Optional[bool] = None


class AddChatRequest(BaseModel):
    chat_id: int
    chat_name: str


class RemoveChatRequest(BaseModel):
    chat_id: int


@router.get("/config")
async def get_config():
    """Get current autopost configuration"""
    config = autopost_service.get_config()
    next_run = autopost_service.get_next_run_time()
    
    return {
        **config,
        "next_run": next_run.isoformat() if next_run else None
    }


@router.put("/config")
async def update_config(data: UpdateConfigRequest):
    """Update autopost configuration"""
    return autopost_service.update_config(
        enabled=data.enabled,
        message_text=data.message_text,
        chat_ids=data.chat_ids,
        chat_names=data.chat_names,
        schedule_time=data.schedule_time,
        interval_seconds=data.interval_seconds,
        randomize_order=data.randomize_order,
        text_variations=data.text_variations,
        ai_rewrite=data.ai_rewrite
    )


@router.post("/chats/add")
async def add_chat(data: AddChatRequest):
    """Add chat to autopost list"""
    return autopost_service.add_chat(data.chat_id, data.chat_name)


@router.post("/chats/remove")
async def remove_chat(data: RemoveChatRequest):
    """Remove chat from autopost list"""
    return autopost_service.remove_chat(data.chat_id)


@router.post("/run")
async def run_autopost_now(background_tasks: BackgroundTasks):
    """Run autopost immediately"""
    if not telegram_service.is_authorized:
        raise HTTPException(status_code=401, detail="Telegram не авторизован")
    
    if autopost_service._is_running:
        raise HTTPException(status_code=400, detail="Автопостинг уже запущен")
    
    # Run in background
    async def run_task():
        await autopost_service.run_autopost(telegram_service)
    
    background_tasks.add_task(run_task)
    
    return {
        "status": "started",
        "message": "Автопостинг запущен",
        "total_chats": len(autopost_service.config.chat_ids)
    }


@router.get("/status")
async def get_run_status():
    """Get current run status"""
    return autopost_service.get_run_status()


@router.post("/stop")
async def stop_autopost():
    """Stop running autopost"""
    autopost_service._is_running = False
    return {"status": "stopped"}


@router.get("/preview")
async def preview_autopost():
    """Preview what will be posted"""
    config = autopost_service.config
    
    chats_preview = []
    for chat_id in config.chat_ids:
        chats_preview.append({
            "chat_id": chat_id,
            "chat_name": config.chat_names.get(chat_id, str(chat_id)),
            "message_preview": autopost_service.get_message_for_chat(chat_id)[:100] + "..."
        })
    
    total_time_seconds = len(config.chat_ids) * config.interval_seconds
    total_time_minutes = total_time_seconds // 60
    
    return {
        "total_chats": len(config.chat_ids),
        "interval_seconds": config.interval_seconds,
        "estimated_duration_minutes": total_time_minutes,
        "schedule_time": config.schedule_time,
        "chats": chats_preview
    }
