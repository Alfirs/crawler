import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .db import get_session
from .models import GenerationJob, Post
from .llm import build_outline, OutlineValidationError
from .image_service import generate_slide_image
from .security import make_signed_token
from .storage import ensure_dirs, save_images_zip, OUT_DIR
from .themes import normalize_theme_id, THEMES


def _update_job(
    job: GenerationJob,
    status: str,
    error: Optional[str] = None,
) -> None:
    job.status = status
    job.error = error
    job.updated_at = datetime.utcnow()


def process_post(post_id: int, job_id: str) -> None:
    ensure_dirs()
    with get_session() as session:
        job = session.get(GenerationJob, job_id)
        post = session.get(Post, post_id)
        if not job or not post:
            return

        _update_job(job, "processing")
        post.status = "processing"
        session.add(job)
        session.add(post)
        session.commit()

        try:
            outline = build_outline(text=post.source_text, slides=post.slides)
            theme_id = normalize_theme_id(outline.get("theme") or post.theme)
            tmp_paths = []
            tmp_dir = OUT_DIR / "_tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            theme_meta = THEMES[theme_id]
            for idx, slide in enumerate(outline.get("slides", [])[: post.slides], start=1):
                out_path = tmp_dir / f"slide_{idx:02d}.png"
                generate_slide_image(slide, theme_meta, out_path)
                tmp_paths.append(out_path.relative_to(Path(__file__).resolve().parent).as_posix())

            zip_path, _, image_public_paths = save_images_zip(tmp_paths, post_id=post.id)
            token = make_signed_token({"post_id": post.id})

            post.status = "ready"
            post.image_paths_json = json.dumps(image_public_paths, ensure_ascii=False)
            post.zip_path = zip_path
            post.share_token = token
            post.share_token_used = False
            post.theme = theme_id
            session.add(post)

            _update_job(job, "ready", error=None)
            session.add(job)
            session.commit()
        except OutlineValidationError as exc:
            session.refresh(post)
            _mark_error(session, post, job, str(exc))
        except Exception as exc:
            _mark_error(session, post, job, str(exc))


def _mark_error(session, post: Post, job: GenerationJob, message: str) -> None:
    post.status = "error"
    job.error = message
    _update_job(job, "error", error=message)
    session.add(post)
    session.add(job)
    session.commit()
