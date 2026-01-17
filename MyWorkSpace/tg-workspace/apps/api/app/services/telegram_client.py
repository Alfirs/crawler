"""
Telegram Client Service using Telethon
Provides live connection to Telegram for reading and sending messages
"""
import asyncio
import os
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient as TelethonClient
from telethon.sessions import StringSession
from telethon.tl.types import User, Chat, Channel, Message
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

# Session file path
SESSION_DIR = Path(__file__).parent.parent.parent / "sessions"
SESSION_DIR.mkdir(exist_ok=True)


class TelegramService:
    """
    Telegram client wrapper for TG Workspace
    """
    
    def __init__(self):
        self.client: Optional[TelethonClient] = None
        self.api_id: Optional[int] = None
        self.api_hash: Optional[str] = None
        self.phone: Optional[str] = None
        self.is_authorized: bool = False
        self.phone_code_hash: Optional[str] = None
        self._message_handlers: List[Callable] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    async def initialize(self, api_id: int, api_hash: str):
        """Initialize client with API credentials"""
        self.api_id = api_id
        self.api_hash = api_hash
        
        session_file = SESSION_DIR / "tg_workspace.session"
        
        self.client = TelethonClient(
            str(session_file),
            api_id,
            api_hash,
            system_version="4.16.30-vxCUSTOM"
        )
        
        await self.client.connect()
        self.is_authorized = await self.client.is_user_authorized()
        
        return {"connected": True, "authorized": self.is_authorized}
    
    async def start_auth(self, phone: str) -> Dict[str, Any]:
        """Start phone authentication"""
        if not self.client:
            raise ValueError("Client not initialized")
            
        self.phone = phone
        
        try:
            result = await self.client.send_code_request(phone)
            self.phone_code_hash = result.phone_code_hash
            
            return {
                "status": "code_sent",
                "phone": phone,
                "message": "Код отправлен в Telegram"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def verify_code(self, code: str) -> Dict[str, Any]:
        """Verify phone code"""
        if not self.client or not self.phone:
            raise ValueError("Auth not started")
            
        try:
            await self.client.sign_in(
                self.phone, 
                code, 
                phone_code_hash=self.phone_code_hash
            )
            self.is_authorized = True
            
            me = await self.client.get_me()
            
            return {
                "status": "authorized",
                "user": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone
                }
            }
        except SessionPasswordNeededError:
            return {
                "status": "2fa_required",
                "message": "Требуется пароль двухфакторной аутентификации"
            }
        except PhoneCodeInvalidError:
            return {
                "status": "error",
                "message": "Неверный код"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def verify_2fa(self, password: str) -> Dict[str, Any]:
        """Verify 2FA password"""
        if not self.client:
            raise ValueError("Client not initialized")
            
        try:
            await self.client.sign_in(password=password)
            self.is_authorized = True
            
            me = await self.client.get_me()
            
            return {
                "status": "authorized",
                "user": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "username": me.username
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def get_auth_status(self) -> Dict[str, Any]:
        """Get current authorization status"""
        if not self.client:
            return {"authorized": False, "connected": False}
            
        connected = self.client.is_connected()
        authorized = await self.client.is_user_authorized() if connected else False
        
        user_info = None
        if authorized:
            me = await self.client.get_me()
            user_info = {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username
            }
        
        return {
            "connected": connected,
            "authorized": authorized,
            "user": user_info
        }
    
    async def logout(self) -> Dict[str, Any]:
        """Logout and clear session"""
        if self.client:
            await self.client.log_out()
            self.is_authorized = False
            
        return {"status": "logged_out"}
    
    async def get_dialogs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of dialogs (chats)"""
        if not self.client or not self.is_authorized:
            raise ValueError("Not authorized")
            
        dialogs = await self.client.get_dialogs(limit=limit)
        
        result = []
        for dialog in dialogs:
            entity = dialog.entity
            
            dialog_type = "user"
            if isinstance(entity, Channel):
                dialog_type = "channel" if entity.broadcast else "group"
            elif isinstance(entity, Chat):
                dialog_type = "group"
            
            result.append({
                "id": dialog.id,
                "name": dialog.name,
                "type": dialog_type,
                "unread_count": dialog.unread_count,
                "last_message": dialog.message.text if dialog.message else None,
                "last_message_date": dialog.message.date.isoformat() if dialog.message else None,
            })
        
        return result
    
    async def get_messages(
        self, 
        chat_id: int, 
        limit: int = 50,
        offset_id: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages from a chat"""
        if not self.client or not self.is_authorized:
            raise ValueError("Not authorized")
            
        messages = await self.client.get_messages(
            chat_id, 
            limit=limit,
            offset_id=offset_id
        )
        
        result = []
        for msg in messages:
            if not msg.text:
                continue
                
            sender_name = "Unknown"
            sender_id = None
            sender_username = None
            
            if msg.sender:
                sender_id = msg.sender.id
                if isinstance(msg.sender, User):
                    sender_name = f"{msg.sender.first_name or ''} {msg.sender.last_name or ''}".strip()
                    sender_username = msg.sender.username
                else:
                    sender_name = getattr(msg.sender, 'title', 'Unknown')
            
            result.append({
                "id": msg.id,
                "date": msg.date.isoformat(),
                "text": msg.text,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "sender_username": sender_username,
                "is_outgoing": msg.out,
                "reply_to_msg_id": msg.reply_to_msg_id if msg.reply_to else None
            })
        
        return result
    
    async def send_message(
        self, 
        chat_id: int, 
        text: str,
        reply_to: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send a message to a chat"""
        if not self.client or not self.is_authorized:
            raise ValueError("Not authorized")
            
        try:
            msg = await self.client.send_message(
                chat_id,
                text,
                reply_to=reply_to
            )
            
            return {
                "status": "sent",
                "message_id": msg.id,
                "date": msg.date.isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def get_entity_info(self, username_or_id) -> Dict[str, Any]:
        """Get info about a user/chat by username or ID"""
        if not self.client or not self.is_authorized:
            raise ValueError("Not authorized")
            
        try:
            entity = await self.client.get_entity(username_or_id)
            
            if isinstance(entity, User):
                return {
                    "type": "user",
                    "id": entity.id,
                    "first_name": entity.first_name,
                    "last_name": entity.last_name,
                    "username": entity.username,
                    "phone": entity.phone,
                    "is_bot": entity.bot
                }
            elif isinstance(entity, (Chat, Channel)):
                return {
                    "type": "group" if isinstance(entity, Chat) else "channel",
                    "id": entity.id,
                    "title": entity.title,
                    "username": getattr(entity, 'username', None)
                }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def add_message_handler(self, handler: Callable):
        """Add handler for new messages"""
        self._message_handlers.append(handler)
        
    async def start_listening(self, chat_ids: Optional[List[int]] = None):
        """Start listening for new messages"""
        if not self.client:
            raise ValueError("Client not initialized")
            
        from telethon import events
        
        @self.client.on(events.NewMessage(chats=chat_ids))
        async def handler(event):
            msg = event.message
            
            sender_name = "Unknown"
            sender_username = None
            
            if msg.sender:
                if isinstance(msg.sender, User):
                    sender_name = f"{msg.sender.first_name or ''} {msg.sender.last_name or ''}".strip()
                    sender_username = msg.sender.username
                    
            message_data = {
                "id": msg.id,
                "chat_id": event.chat_id,
                "date": msg.date.isoformat(),
                "text": msg.text,
                "sender_id": msg.sender_id,
                "sender_name": sender_name,
                "sender_username": sender_username,
            }
            
            for h in self._message_handlers:
                await h(message_data)
        
        await self.client.run_until_disconnected()
    
    async def disconnect(self):
        """Disconnect client"""
        if self.client:
            await self.client.disconnect()


# Global instance
telegram_service = TelegramService()


async def get_telegram_service() -> TelegramService:
    """Get or create telegram service instance"""
    return telegram_service
