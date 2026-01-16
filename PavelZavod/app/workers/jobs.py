from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.models.draft_post import DraftPost, DraftStatus
from app.services.image_client import ImageClient
from app.services.llm_client import LLMClient
from app.services.publisher import Publisher
from app.services.threads_client import ThreadsClient


def _publish_single(session: Session, draft: DraftPost, publisher: Publisher, image_client: ImageClient) -> None:
    image_url = image_client.generate_image(draft.image_prompt or "Cyberpunk newsroom, neon lights")
    publisher.publish_to_threads(draft)
    publisher.publish_to_tenchat(draft)
    publisher.publish_to_telegram(draft, image_url=image_url)
    draft.status = DraftStatus.PUBLISHED
    session.commit()


def sync_threads_top(topic: str = "ai", limit: int = 5) -> None:
    """Fetch top Threads posts and store/update draft records."""

    engine = get_engine()
    settings = get_settings()
    threads_client = ThreadsClient()
    llm_client = LLMClient(api_key=settings.llm_api_key)

    posts = threads_client.fetch_top_threads(topic=topic, limit=limit)

    with Session(engine) as session:
        for post in posts:
            draft = session.query(DraftPost).filter_by(source_id=post.id).first()
            if not draft:
                draft = DraftPost(
                    source_id=post.id,
                    source_url=post.url,
                    raw_text_en=post.text,
                )
                session.add(draft)

            rewrite = llm_client.rewrite_post(post.text)
            draft.translated_text_ru = rewrite["translated_text"]
            draft.short_hook = rewrite["hook"]
            draft.body_ru = rewrite["body"]
            draft.cta_ru = rewrite["cta"]
            draft.image_prompt = rewrite["image_prompt"]
            draft.status = DraftStatus.NEW
        session.commit()


def publish_draft(draft_id: int) -> None:
    """Publish a specific draft when it has been approved."""

    engine = get_engine()
    publisher = Publisher()
    image_client = ImageClient()

    with Session(engine) as session:
        draft = session.get(DraftPost, draft_id)
        if not draft or draft.status != DraftStatus.APPROVED:
            return
        _publish_single(session, draft, publisher, image_client)


def publish_approved_posts() -> None:
    """Publish all drafts currently approved."""

    engine = get_engine()
    publisher = Publisher()
    image_client = ImageClient()

    with Session(engine) as session:
        drafts = (
            session.query(DraftPost)
            .filter(DraftPost.status == DraftStatus.APPROVED)
            .all()
        )
        for draft in drafts:
            _publish_single(session, draft, publisher, image_client)
