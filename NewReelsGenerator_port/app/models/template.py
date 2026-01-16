"""SQLAlchemy-модель шаблонов для видео и каруселей."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String(50), nullable=False, default="video")
    is_public = Column(Boolean, default=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Настройки для видео-контента
    mask_x = Column(Integer, nullable=True)
    mask_y = Column(Integer, nullable=True)
    mask_width = Column(Integer, nullable=True)
    mask_height = Column(Integer, nullable=True)

    caption_mask_x = Column(Integer, nullable=True)
    caption_mask_y = Column(Integer, nullable=True)
    caption_mask_width = Column(Integer, nullable=True)
    caption_mask_height = Column(Integer, nullable=True)

    title_font = Column(String(255), nullable=True)
    title_size = Column(Integer, nullable=True)
    caption_size = Column(Integer, nullable=True)
    text_color = Column(String(32), nullable=True)
    box_color = Column(String(32), nullable=True)
    box_alpha = Column(Integer, nullable=True)
    full_vertical = Column(Boolean, nullable=True)
    gradient_height = Column(Integer, nullable=True)
    gradient_strength = Column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Template id={self.id} name={self.name!r} type={self.type} "
            f"public={self.is_public}>"
        )

