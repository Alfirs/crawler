"""
SQLAlchemy Database Models for TG Workspace
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Date, Boolean, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.db.database import Base


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    CALL_SCHEDULED = "CALL_SCHEDULED"
    WON = "WON"
    LOST = "LOST"


class LeadType(str, enum.Enum):
    TASK = "TASK"
    VACANCY = "VACANCY"
    OFFER = "OFFER"
    SPAM = "SPAM"
    CHATTER = "CHATTER"


class LeadCategory(str, enum.Enum):
    BOTS_TG_WA_VK = "Bots_TG_WA_VK"
    LANDING_SITES = "Landing_Sites"
    PARSING_ANALYTICS = "Parsing_Analytics_Reports"
    INTEGRATIONS = "Integrations_Sheets_CRM_n8n"
    SALES_CRM = "Sales_CRM_Process"
    AUTOPOSTING = "Autoposting_ContentFactory"
    OTHER = "Other"


class TaskType(str, enum.Enum):
    FOLLOWUP = "FOLLOWUP"
    CALL = "CALL"
    REMINDER = "REMINDER"


class GoalMode(str, enum.Enum):
    LITE = "lite"
    NORMAL = "normal"
    HARD = "hard"


# ============== CORE MODELS ==============

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sources = relationship("Source", back_populates="workspace", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="workspace", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    type = Column(String(50), nullable=False)  # 'telegram_json', 'telegram_html', 'link'
    title = Column(String(255), nullable=False)
    link = Column(String(512), nullable=True)
    file_path = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    parsed_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)

    workspace = relationship("Workspace", back_populates="sources")
    messages = relationship("Message", back_populates="source", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    msg_id = Column(String(100), nullable=True)  # Original message ID from Telegram
    date = Column(DateTime, nullable=True)
    author = Column(String(255), nullable=True)
    author_id = Column(String(100), nullable=True)
    text = Column(Text, nullable=True)
    raw_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Source", back_populates="messages")
    lead = relationship("Lead", back_populates="message", uselist=False)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    
    # Classification
    type = Column(String(50), default=LeadType.CHATTER.value)
    category = Column(String(100), default=LeadCategory.OTHER.value)
    
    # Scoring (0.0 - 1.0)
    fit_score = Column(Float, default=0.0)
    money_score = Column(Float, default=0.0)
    recency_score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)  # Combined weighted score
    
    # CRM Status
    status = Column(String(50), default=LeadStatus.NEW.value)
    status_changed_at = Column(DateTime, nullable=True)
    
    # Anti-spam
    do_not_contact = Column(Boolean, default=False)
    dnc_reason = Column(String(255), nullable=True)
    last_contacted_at = Column(DateTime, nullable=True)
    contact_count = Column(Integer, default=0)
    
    # Deal info
    expected_revenue = Column(Float, nullable=True)
    lost_reason = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="leads")
    message = relationship("Message", back_populates="lead")
    outreach_history = relationship("Outreach", back_populates="lead", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="lead", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="lead", cascade="all, delete-orphan")


class Outreach(Base):
    __tablename__ = "outreach"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    
    message_text = Column(Text, nullable=False)
    channel = Column(String(50), default="telegram")
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)  # Draft created
    sent_at = Column(DateTime, nullable=True)  # When user confirmed sending
    
    # Result tracking
    result_status = Column(String(50), nullable=True)  # 'sent', 'replied', 'no_reply'
    replied_at = Column(DateTime, nullable=True)
    
    lead = relationship("Lead", back_populates="outreach_history")
    template = relationship("Template")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="notes")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    
    type = Column(String(50), default=TaskType.FOLLOWUP.value)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    due_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="pending")  # 'pending', 'completed', 'skipped'
    
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="tasks")


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    text = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True)  # List of variable names like ['name', 'project']
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, nullable=True)  # Based on reply rate
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============== GAMIFICATION MODELS ==============

class UserProgress(Base):
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True, index=True)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    streak_days = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_active_date = Column(Date, nullable=True)
    
    # Lifetime stats
    total_outreach = Column(Integer, default=0)
    total_replies = Column(Integer, default=0)
    total_won = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Badge(Base):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    icon = Column(String(50), nullable=True)  # Emoji or icon name
    condition_type = Column(String(50), nullable=False)  # 'streak', 'outreach', 'won', 'revenue'
    condition_value = Column(Integer, nullable=False)
    earned_at = Column(DateTime, nullable=True)
    is_earned = Column(Boolean, default=False)


class DailyGoal(Base):
    __tablename__ = "daily_goals"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False)
    
    # Goals
    messages_target = Column(Integer, default=20)
    followups_target = Column(Integer, default=5)
    moves_target = Column(Integer, default=1)  # Funnel movements
    
    # Progress
    messages_done = Column(Integer, default=0)
    followups_done = Column(Integer, default=0)
    moves_done = Column(Integer, default=0)
    
    # Completion
    is_completed = Column(Boolean, default=False)
    xp_earned = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class WeeklyGoal(Base):
    __tablename__ = "weekly_goals"

    id = Column(Integer, primary_key=True, index=True)
    week_start = Column(Date, unique=True, nullable=False)
    
    messages_target = Column(Integer, default=100)
    followups_target = Column(Integer, default=25)
    calls_target = Column(Integer, default=3)
    
    messages_done = Column(Integer, default=0)
    followups_done = Column(Integer, default=0)
    calls_done = Column(Integer, default=0)
    
    is_completed = Column(Boolean, default=False)


class MonthlyGoal(Base):
    __tablename__ = "monthly_goals"

    id = Column(Integer, primary_key=True, index=True)
    month_start = Column(Date, unique=True, nullable=False)
    
    revenue_target = Column(Float, default=100000.0)
    wins_target = Column(Integer, default=5)
    
    revenue_done = Column(Float, default=0.0)
    wins_done = Column(Integer, default=0)
    
    is_completed = Column(Boolean, default=False)
