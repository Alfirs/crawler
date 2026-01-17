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
        
        # Save credentials to .env for persistence
        self._update_env_file(api_id, api_hash)
        
        await self._init_client()
        return {"connected": True, "authorized": self.is_authorized}

    async def startup(self):
        """Auto-startup: Load credentials from env and connect if possible"""
        import os
        from dotenv import load_dotenv
        
        # Reload env to be sure
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        load_dotenv(env_path)
        
        api_id_str = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        
        if api_id_str and api_hash:
            try:
                self.api_id = int(api_id_str)
                self.api_hash = api_hash
                print(f"DEBUG: Auto-initializing Telegram client with ID: {self.api_id}")
                await self._init_client()
            except Exception as e:
                print(f"ERROR: Auto-startup failed: {e}")

    async def _init_client(self):
        """Internal client initialization logic"""
        if not self.api_id or not self.api_hash:
            raise ValueError("API credentials missing")

        session_file = SESSION_DIR / "tg_workspace.session"
        print(f"DEBUG: Resolving session file: {session_file.absolute()}")
        
        self.client = TelethonClient(
            str(session_file),
            self.api_id,
            self.api_hash,
            system_version="Windows 11",
            device_model="Desktop",
            app_version="5.0.1",
            lang_code="en",
            system_lang_code="en"
        )
        
        try:
            await self.client.connect()
            self.is_authorized = await self.client.is_user_authorized()
            print(f"DEBUG: Client connected. Authorized: {self.is_authorized}")
        except Exception as e:
            print(f"ERROR: Connection failed: {e}")
            self.client = None
            raise

    def _update_env_file(self, api_id: int, api_hash: str):
        """Update .env file with new credentials"""
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        
        try:
            # Read existing
            lines = []
            if env_path.exists():
                with open(env_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            
            # Remove existing keys
            lines = [l for l in lines if not l.startswith("TELEGRAM_API_ID=") and not l.startswith("TELEGRAM_API_HASH=")]
            
            # Append new
            if lines and not lines[-1].endswith('\n'):
                lines[-1] += '\n'
            
            lines.append(f"\n# Telegram Credentials\n")
            lines.append(f"TELEGRAM_API_ID={api_id}\n")
            lines.append(f"TELEGRAM_API_HASH={api_hash}\n")
            
            # Write back
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            print(f"DEBUG: Setup updated .env at {env_path}")
            
        except Exception as e:
            print(f"ERROR: Failed to update .env: {e}")
    
    async def start_auth(self, phone: str) -> Dict[str, Any]:
        """Start phone authentication"""
        if not self.client:
            raise ValueError("Client not initialized")
            
        self.phone = phone
        
        try:
            result = await self.client.send_code_request(phone)
            print(f"DEBUG: Send code result type: {type(result)}")
            print(f"DEBUG: Phone code hash: {result.phone_code_hash}")
            if hasattr(result, 'type'):
                print(f"DEBUG: Code delivery type: {result.type}")
            if hasattr(result, 'next_type'):
                print(f"DEBUG: Next code type: {result.next_type}")
            if hasattr(result, 'timeout'):
                print(f"DEBUG: Timeout: {result.timeout}")
                
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

    async def start_qr_auth(self) -> Dict[str, Any]:
        """Start QR code authentication"""
        if not self.client:
            raise ValueError("Client not initialized")
            
        try:
            if not self.client.is_connected():
                await self.client.connect()
                
            qr_login = await self.client.qr_login()
            self._qr_login = qr_login
            self._qr_status = {"status": "waiting", "message": "Waiting for scan"}
            
            # Cancel existing task if any
            if hasattr(self, '_qr_task') and self._qr_task:
                self._qr_task.cancel()
                
            # Start background monitoring
            self._qr_task = asyncio.create_task(self._monitor_qr_login(qr_login))
            
            return {
                "status": "qr_generated",
                "url": qr_login.url,
                "token_base64": qr_login.url 
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    async def _monitor_qr_login(self, qr_login):
        """Background task to wait for QR scan"""
        print("DEBUG: Starting QR monitor task")
        try:
            # This waits indefinitely until scan or error
            user = await qr_login.wait()
            print(f"DEBUG: QR Scan success! User: {user}")
            
            self.is_authorized = True
            me = await self.client.get_me()
            self._qr_status = {
                "status": "authorized",
                "user": {
                    "id": me.id,
                    "username": me.username
                }
            }
            
        except SessionPasswordNeededError:
            print("DEBUG: SessionPasswordNeededError in background task")
            self._qr_status = {
                "status": "2fa_required",
                "message": "Two-step verification required"
            }
            
        except Exception as e:
            print(f"DEBUG: QR Monitor Error: {e}")
            if "expired" in str(e).lower():
                self._qr_status = {"status": "expired", "message": "QR code expired"}
            else:
                self._qr_status = {"status": "error", "message": str(e)}

    async def check_qr_auth(self) -> Dict[str, Any]:
        """Check status of QR authentication"""
        if not hasattr(self, '_qr_status'):
             # Fallback if task hasn't started
             return {"status": "waiting", "message": "Initializing..."}
             
        # If still waiting, double check actual auth state just in case
        if self._qr_status["status"] == "waiting":
             if self.client and await self.client.is_user_authorized():
                 self.is_authorized = True
                 me = await self.client.get_me()
                 self._qr_status = {
                    "status": "authorized",
                    "user": {
                        "id": me.id,
                        "username": me.username
                    }
                }

        return self._qr_status
    
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

    async def import_history_stream(
        self, 
        link: str, 
        limit: int = 100, 
        offset_date: Optional[datetime] = None,
        batch_size: int = 50
    ):
        """
        Stream history from a chat link in batches
        Yields dict with messages batch and metadata
        """
        if not self.client or not self.is_authorized:
            raise ValueError("Not authorized")
            
        try:
            # 1. Resolve entity
            entity = await self.client.get_entity(link)
            
            # 2. Get basic info
            chat_title = getattr(entity, 'title', None)
            if not chat_title:
                chat_title = f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip()
            
            # 3. Iterate messages
            current_batch = []
            
            async for msg in self.client.iter_messages(entity, limit=limit):
                if offset_date and msg.date.replace(tzinfo=None) < offset_date.replace(tzinfo=None):
                    break
                    
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
                
                current_batch.append({
                    "id": msg.id, # Message ID in chat
                    "date": msg.date.isoformat(),
                    "text": msg.text,
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "sender_username": sender_username,
                    "is_outgoing": msg.out,
                    "reply_to_msg_id": msg.reply_to_msg_id if msg.reply_to else None,
                    "raw_json": {
                        "id": msg.id,
                        "date": msg.date.isoformat(),
                        "chat_id": entity.id
                    }
                })

                if len(current_batch) >= batch_size:
                    yield {
                        "status": "success",
                        "chat_title": chat_title,
                        "chat_id": entity.id,
                        "messages": current_batch
                    }
                    current_batch = []
            
            # Yield remaining
            if current_batch:
                yield {
                    "status": "success",
                    "chat_title": chat_title,
                    "chat_id": entity.id,
                    "messages": current_batch
                }
            
        except Exception as e:
            yield {
                "status": "error",
                "message": str(e)
            }


# Global instance
telegram_service = TelegramService()


async def get_telegram_service() -> TelegramService:
    """Get or create telegram service instance"""
    return telegram_service
