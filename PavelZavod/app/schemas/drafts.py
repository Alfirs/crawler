from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.draft_post import DraftStatus


class DraftPostBase(BaseModel):
    source_id: str
    source_url: str
    raw_text_en: str
    translated_text_ru: Optional[str]
    short_hook: Optional[str]
    body_ru: Optional[str]
    cta_ru: Optional[str]
    image_prompt: Optional[str]
    status: DraftStatus

    class Config:
        from_attributes = True


class DraftPostOut(DraftPostBase):
    id: int
    created_at: datetime
    updated_at: datetime
