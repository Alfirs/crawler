from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SourceIn(BaseModel):
    kind: str  # currently only "text"
    text: Optional[str] = None


class GenerateIn(BaseModel):
    format: str = "carousel"
    slides: int = 6
    source: SourceIn
    theme: Optional[str] = None


class SlideBlock(BaseModel):
    templateId: Optional[str] = None
    layout: Optional[str] = None
    label: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    body: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    cta: Optional[str] = None
    notes: Optional[str] = None
    blocksOrder: Optional[List[str]] = None


class SlidesPayload(BaseModel):
    slides: List[SlideBlock]
    settings: Dict[str, Any] = Field(default_factory=dict)


class GenerateOut(BaseModel):
    post_id: int
    status: str
    share_url: str
    token: str


class PostOut(BaseModel):
    id: int
    type: str
    status: str
    slides: int
    share_url: Optional[str] = None
    theme: Optional[str] = None


class PostEditorOut(PostOut):
    source_text: Optional[str] = None
    data: SlidesPayload


class PostUpdateIn(BaseModel):
    slides: Optional[List[SlideBlock]] = None
    settings: Optional[Dict[str, Any]] = None
    theme: Optional[str] = None


class ExportIn(BaseModel):
    format: str = "png"  # png | pdf
    range: str = "all"  # all | current


class ExportOut(BaseModel):
    status: str
    detail: Optional[str] = None


class AIActionIn(BaseModel):
    field: str  # title | subtitle | body | cta
    action: str  # improve | shorten | expand | simplify
    value: str


class AIActionOut(BaseModel):
    field: str
    action: str
    value: str


class BackgroundUploadOut(BaseModel):
    url: str
