"""
Autopost Service - Scheduled posting to multiple chats
"""
import asyncio
import json
import random
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import threading
from app.services.llm import paraphrase_message

# Config file path
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
CONFIG_DIR.mkdir(exist_ok=True)
AUTOPOST_CONFIG = CONFIG_DIR / "autopost.json"


@dataclass
class AutopostConfig:
    """Autopost configuration"""
    enabled: bool = False
    message_text: str = ""
    chat_ids: List[int] = None
    chat_names: Dict[int, str] = None  # id -> name mapping
    schedule_time: str = "10:00"  # HH:MM format
    interval_seconds: int = 180  # seconds between posts (default 3 min)
    randomize_order: bool = True
    text_variations: List[str] = None  # Optional variations
    ai_rewrite: bool = False  # Use AI to rewrite message for each chat
    last_run: Optional[str] = None
    
    def __post_init__(self):
        if self.chat_ids is None:
            self.chat_ids = []
            

        if self.chat_names is None:
            self.chat_names = {}
        if self.text_variations is None:
            self.text_variations = []


class AutopostService:
    """Service for scheduled autoposting"""
    
    def __init__(self):
        self.config = self._load_config()
        self._scheduler_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._current_run_log: List[Dict] = []
        
    def _load_config(self) -> AutopostConfig:
        """Load config from file"""
        if AUTOPOST_CONFIG.exists():
            try:
                with open(AUTOPOST_CONFIG, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return AutopostConfig(**data)
            except Exception as e:
                print(f"Error loading autopost config: {e}")
        return AutopostConfig()
    
    def _save_config(self):
        """Save config to file"""
        with open(AUTOPOST_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.config), f, ensure_ascii=False, indent=2)
    
    def get_config(self) -> Dict[str, Any]:
        """Get current config as dict"""
        return asdict(self.config)
    
    def update_config(
        self,
        enabled: Optional[bool] = None,
        message_text: Optional[str] = None,
        chat_ids: Optional[List[int]] = None,
        chat_names: Optional[Dict[int, str]] = None,
        schedule_time: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        randomize_order: Optional[bool] = None,
        text_variations: Optional[List[str]] = None,
        ai_rewrite: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update config"""
        if enabled is not None:
            self.config.enabled = enabled
        if message_text is not None:
            self.config.message_text = message_text
        if chat_ids is not None:
            self.config.chat_ids = chat_ids
        if chat_names is not None:
            self.config.chat_names = chat_names
        if schedule_time is not None:
            self.config.schedule_time = schedule_time
        if interval_seconds is not None:
            self.config.interval_seconds = max(60, interval_seconds)  # Min 60 sec to prevent bans
        if randomize_order is not None:
            self.config.randomize_order = randomize_order
        if text_variations is not None:
            self.config.text_variations = text_variations
        if ai_rewrite is not None:
            self.config.ai_rewrite = ai_rewrite
            
        self._save_config()
        return self.get_config()
    
    def add_chat(self, chat_id: int, chat_name: str) -> Dict[str, Any]:
        """Add chat to autopost list"""
        if chat_id not in self.config.chat_ids:
            self.config.chat_ids.append(chat_id)
        self.config.chat_names[chat_id] = chat_name
        self._save_config()
        return {"added": True, "chat_id": chat_id, "chat_name": chat_name}
    
    def remove_chat(self, chat_id: int) -> Dict[str, Any]:
        """Remove chat from autopost list"""
        if chat_id in self.config.chat_ids:
            self.config.chat_ids.remove(chat_id)
        if chat_id in self.config.chat_names:
            del self.config.chat_names[chat_id]
        self._save_config()
        return {"removed": True, "chat_id": chat_id}
    
    def get_message_for_chat(self, chat_id: int) -> str:
        """Get message text, optionally with variation"""
        if self.config.text_variations:
            # Pick random variation
            return random.choice([self.config.message_text] + self.config.text_variations)
        return self.config.message_text
    
    async def run_autopost(self, telegram_service) -> Dict[str, Any]:
        """Execute autopost to all configured chats"""
        if not self.config.chat_ids:
            return {"status": "error", "message": "Нет чатов для постинга"}
        
        if not self.config.message_text:
            return {"status": "error", "message": "Нет текста сообщения"}
        
        self._is_running = True
        self._current_run_log = []
        
        chat_ids = self.config.chat_ids.copy()
        if self.config.randomize_order:
            random.shuffle(chat_ids)
        
        success_count = 0
        error_count = 0
        
        for i, chat_id in enumerate(chat_ids):
            chat_name = self.config.chat_names.get(chat_id, str(chat_id))
            message = self.get_message_for_chat(chat_id)
            
            # AI Paraphrasing (Silver Bullet)
            if self.config.ai_rewrite:
                try:
                    message = paraphrase_message(message)
                except Exception as e:
                    print(f"AI Paraphrase failed, using original: {e}")
            
            log_entry = {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "time": datetime.now().isoformat(),
                "status": "pending"
            }
            
            try:
                result = await telegram_service.send_message(chat_id, message)
                
                if result.get("status") == "sent":
                    log_entry["status"] = "success"
                    log_entry["message_id"] = result.get("message_id")
                    success_count += 1
                else:
                    log_entry["status"] = "error"
                    log_entry["error"] = result.get("message", "Unknown error")
                    error_count += 1
                    
            except Exception as e:
                log_entry["status"] = "error"
                log_entry["error"] = str(e)
                error_count += 1
            
            self._current_run_log.append(log_entry)
            
            # Wait before next chat (except for last one)
            if i < len(chat_ids) - 1:
                # Add +/- 10s jitter for natural behavior
                jitter = random.randint(-10, 10)
                wait_time = max(60, self.config.interval_seconds + jitter)
                await asyncio.sleep(wait_time)
        
        self._is_running = False
        self.config.last_run = datetime.now().isoformat()
        self._save_config()
        
        return {
            "status": "completed",
            "success_count": success_count,
            "error_count": error_count,
            "total": len(chat_ids),
            "log": self._current_run_log
        }
    
    def get_run_status(self) -> Dict[str, Any]:
        """Get current run status"""
        return {
            "is_running": self._is_running,
            "log": self._current_run_log,
            "last_run": self.config.last_run
        }
    
    def get_next_run_time(self) -> Optional[datetime]:
        """Calculate next scheduled run time"""
        if not self.config.enabled or not self.config.schedule_time:
            return None
            
        try:
            hour, minute = map(int, self.config.schedule_time.split(":"))
            now = datetime.now()
            scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If time already passed today, schedule for tomorrow
            if scheduled <= now:
                scheduled += timedelta(days=1)
                
            return scheduled
        except:
            return None


# Global instance
autopost_service = AutopostService()
