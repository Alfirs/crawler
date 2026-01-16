from enum import Enum
from typing import Optional

from sqlalchemy import Enum as SqlEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DraftStatus(str, Enum):
    """Workflow status of a draft post."""

    NEW = "new"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class DraftPost(TimestampMixin, Base):
    """Draft post generated from Threads content."""

    __tablename__ = "draft_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    source_url: Mapped[str] = mapped_column(String(512))
    raw_text_en: Mapped[str] = mapped_column(Text)
    translated_text_ru: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_hook: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)
    body_ru: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cta_ru: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)
    image_prompt: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[DraftStatus] = mapped_column(
        SqlEnum(DraftStatus), default=DraftStatus.NEW, nullable=False
    )
