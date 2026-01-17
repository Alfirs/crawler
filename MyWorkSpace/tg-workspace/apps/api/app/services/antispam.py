"""
Anti-Spam Protection Service
Enforces limits and prevents ban-triggering behavior
"""
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from app.db.models import Lead, Outreach, Setting, DailyGoal

logger = logging.getLogger(__name__)

# Default limits (can be overridden in settings)
DEFAULT_DAILY_LIMIT = 15
DEFAULT_FOLLOWUP_COOLDOWN_HOURS = 48
MAX_SAFE_DAILY_LIMIT = 25  # Warning threshold
ABSOLUTE_MAX_DAILY_LIMIT = 40  # Hard ceiling


class AntiSpamService:
    """Service to enforce anti-spam rules"""
    
    def __init__(self, db: Session):
        self.db = db
        self._load_settings()
    
    def _load_settings(self):
        """Load settings from database"""
        self.daily_limit = self._get_setting("daily_limit", DEFAULT_DAILY_LIMIT)
        self.followup_cooldown = self._get_setting("followup_cooldown_hours", DEFAULT_FOLLOWUP_COOLDOWN_HOURS)
    
    def _get_setting(self, key: str, default: int) -> int:
        """Get setting value from database"""
        setting = self.db.query(Setting).filter(Setting.key == key).first()
        if setting:
            try:
                return int(setting.value)
            except:
                return default
        return default
    
    def get_today_sent_count(self) -> int:
        """Count messages sent today"""
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        count = self.db.query(Outreach).filter(
            Outreach.sent_at >= today_start,
            Outreach.sent_at != None
        ).count()
        
        return count
    
    def get_remaining_quota(self) -> Dict[str, Any]:
        """Get remaining daily quota with warnings"""
        sent_today = self.get_today_sent_count()
        remaining = max(0, self.daily_limit - sent_today)
        usage_percent = (sent_today / self.daily_limit * 100) if self.daily_limit > 0 else 100
        
        result = {
            "sent_today": sent_today,
            "daily_limit": self.daily_limit,
            "remaining": remaining,
            "usage_percent": round(usage_percent, 1),
            "can_send": remaining > 0,
            "warning": None
        }
        
        # Add warnings
        if usage_percent >= 100:
            result["warning"] = "⛔ Дневной лимит исчерпан. Подождите до завтра."
        elif usage_percent >= 80:
            result["warning"] = f"⚠️ Осталось {remaining} сообщений на сегодня. Будьте осторожны."
        elif usage_percent >= 60:
            result["warning"] = f"📊 Использовано {int(usage_percent)}% дневного лимита."
        
        return result
    
    def can_contact_lead(self, lead: Lead) -> Tuple[bool, str]:
        """
        Check if we can contact this lead
        Returns (can_contact, reason)
        """
        # Check Do Not Contact
        if lead.do_not_contact:
            return False, f"🚫 В списке 'Не беспокоить': {lead.dnc_reason or 'без причины'}"
        
        # Check daily limit
        quota = self.get_remaining_quota()
        if not quota["can_send"]:
            return False, quota["warning"]
        
        # Check follow-up cooldown
        if lead.last_contacted_at:
            cooldown_end = lead.last_contacted_at + timedelta(hours=self.followup_cooldown)
            if datetime.utcnow() < cooldown_end:
                hours_left = (cooldown_end - datetime.utcnow()).total_seconds() / 3600
                return False, f"⏰ Подождите {int(hours_left)} ч. до следующего сообщения"
        
        return True, "✅ Можно писать"
    
    def check_message_uniqueness(self, lead_id: int, message_text: str) -> Tuple[bool, str]:
        """
        Check if message is unique (not sent before to this lead or recently to others)
        """
        # Normalize text for comparison
        normalized = self._normalize_text(message_text)
        
        # Check if exact message was sent to this lead
        exact_match = self.db.query(Outreach).filter(
            Outreach.lead_id == lead_id,
            Outreach.message_text == message_text
        ).first()
        
        if exact_match:
            return False, "🔄 Это сообщение уже отправлялось этому контакту"
        
        # Check for very similar messages in last 24h
        yesterday = datetime.utcnow() - timedelta(hours=24)
        recent_messages = self.db.query(Outreach).filter(
            Outreach.sent_at >= yesterday
        ).all()
        
        for msg in recent_messages:
            if self._calculate_similarity(normalized, self._normalize_text(msg.message_text)) > 0.9:
                return False, "⚠️ Очень похожее сообщение отправлено недавно. Персонализируйте текст."
        
        return True, "✅ Сообщение уникально"
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        import re
        # Remove extra whitespace, lowercase
        text = re.sub(r'\s+', ' ', text.lower().strip())
        # Remove punctuation for comparison
        text = re.sub(r'[^\w\s]', '', text)
        return text
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity ratio"""
        if not text1 or not text2:
            return 0.0
        
        # Simple word overlap
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def record_outreach_sent(self, lead: Lead, outreach: Outreach):
        """Record that an outreach was sent"""
        now = datetime.utcnow()
        
        # Update lead
        lead.last_contacted_at = now
        lead.contact_count = (lead.contact_count or 0) + 1
        
        # Update outreach
        outreach.sent_at = now
        outreach.result_status = 'sent'
        
        # Update daily goal
        today = date.today()
        daily_goal = self.db.query(DailyGoal).filter(DailyGoal.date == today).first()
        
        if daily_goal:
            if lead.contact_count == 1:
                daily_goal.messages_done += 1
            else:
                daily_goal.followups_done += 1
        
        self.db.commit()
    
    def add_to_dnc_list(self, lead: Lead, reason: str = "Отказ"):
        """Add lead to Do Not Contact list"""
        lead.do_not_contact = True
        lead.dnc_reason = reason
        lead.status = "LOST"
        lead.lost_reason = reason
        
        self.db.commit()
        logger.info(f"Lead {lead.id} added to DNC list: {reason}")
    
    def get_risk_assessment(self) -> Dict[str, Any]:
        """Get overall risk assessment for account safety"""
        quota = self.get_remaining_quota()
        
        # Calculate risk factors
        risk_score = 0
        warnings = []
        
        # High volume today
        if quota["usage_percent"] >= 80:
            risk_score += 30
            warnings.append("Высокий объем сообщений сегодня")
        
        # Check reply rate (low reply rate = spam signals)
        week_ago = datetime.utcnow() - timedelta(days=7)
        sent_week = self.db.query(Outreach).filter(
            Outreach.sent_at >= week_ago
        ).count()
        
        replied_week = self.db.query(Outreach).filter(
            Outreach.sent_at >= week_ago,
            Outreach.result_status == 'replied'
        ).count()
        
        if sent_week > 20:
            reply_rate = replied_week / sent_week if sent_week > 0 else 0
            if reply_rate < 0.05:  # Less than 5% reply rate
                risk_score += 40
                warnings.append(f"Низкий процент ответов ({int(reply_rate*100)}%)")
            elif reply_rate < 0.10:
                risk_score += 20
                warnings.append(f"Процент ответов ниже нормы ({int(reply_rate*100)}%)")
        
        # Determine risk level
        if risk_score >= 60:
            level = "HIGH"
            recommendation = "⚠️ Рекомендуем снизить активность и улучшить персонализацию сообщений"
        elif risk_score >= 30:
            level = "MEDIUM"
            recommendation = "📊 Следите за реакцией получателей. Персонализируйте сообщения."
        else:
            level = "LOW"
            recommendation = "✅ Риск минимальный. Продолжайте в том же духе!"
        
        return {
            "risk_score": risk_score,
            "risk_level": level,
            "warnings": warnings,
            "recommendation": recommendation,
            "stats": {
                "sent_this_week": sent_week,
                "replied_this_week": replied_week,
                "reply_rate": round(replied_week / sent_week * 100, 1) if sent_week > 0 else 0
            }
        }
    
    def validate_new_limit(self, new_limit: int) -> Tuple[bool, str]:
        """Validate if new daily limit is safe"""
        if new_limit > ABSOLUTE_MAX_DAILY_LIMIT:
            return False, f"⛔ Максимально допустимый лимит: {ABSOLUTE_MAX_DAILY_LIMIT}"
        
        if new_limit > MAX_SAFE_DAILY_LIMIT:
            return True, f"⚠️ Лимит {new_limit} выше рекомендуемого ({MAX_SAFE_DAILY_LIMIT}). Риск ограничений в Telegram."
        
        return True, f"✅ Лимит {new_limit} в безопасных пределах"
