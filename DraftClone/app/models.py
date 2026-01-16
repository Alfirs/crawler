from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


class Post(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str
    status: str = "queued"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source_kind: str
    source_text: str
    slides: int
    theme: str = "midnight"
    share_token: Optional[str] = None
    share_token_used: bool = False
    zip_path: Optional[str] = None
    image_paths_json: Optional[str] = None


class GenerationJob(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    post_id: int = Field(foreign_key="post.id")
    status: str = "queued"
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
