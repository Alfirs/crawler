import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import SQLModel

from .db import BASE_DIR, engine, get_session
from .llm import OutlineValidationError, build_outline
from .models import Post
from .schemas import (
    AIActionIn,
    AIActionOut,
    BackgroundUploadOut,
    ExportIn,
    ExportOut,
    GenerateIn,
    GenerateOut,
    PostEditorOut,
    PostOut,
    PostUpdateIn,
    SlidesPayload,
)
from .security import make_signed_token, verify_token
from .storage import ASSETS_ROOT, ensure_dirs, save_background_image
from .themes import DEFAULT_THEME, THEMES, normalize_theme_id, resolve_theme

APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")

app = FastAPI(title="Draft Clone API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/assets", StaticFiles(directory=str(ASSETS_ROOT)), name="assets")

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)

SQLModel.metadata.create_all(engine)
ensure_dirs()


def _share_url(post: Optional[Post]) -> Optional[str]:
    if not post or not post.share_token:
        return None
    return f"{APP_URL}/posts/{post.id}/editor?token={post.share_token}"


def _default_background(palette: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "color",
        "value": palette.get("background"),
        "imageUrl": None,
        "gradient": None,
    }


def _default_brand_kit(theme_key: str, palette: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "activeId": "brand-default",
        "presets": [
            {
                "id": "brand-default",
                "name": f"{theme_key.title()} base",
                "palette": palette,
                "typography": {"title": "Montserrat", "body": "PT Sans"},
                "background": _default_background(palette),
            }
        ],
    }


def _base_settings(theme_id: Optional[str]) -> Dict[str, Any]:
    theme_key = normalize_theme_id(theme_id or DEFAULT_THEME)
    palette = resolve_theme(theme_key)
    background = _default_background(palette)
    return {
        "theme": theme_key,
        "palette": palette,
        "layout": "stacked",
        "typography": {"title": "Montserrat", "body": "PT Sans"},
        "background": background,
        "backgroundLibrary": {
            "colors": [palette["background"]],
            "gradients": [],
            "images": [],
        },
        "brandKit": _default_brand_kit(theme_key, palette),
        "watermark": {"enabled": False, "text": "DraftClone"},
        "applyToAll": True,
    }


def _normalize_payload(raw: Optional[str], fallback_theme: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {"slides": [], "settings": _base_settings(fallback_theme)}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}

    if isinstance(payload, list):
        slides = []
        for idx, value in enumerate(payload, start=1):
            slides.append(
                {
                    "layout": "image",
                    "title": f"Slide {idx}",
                    "body": str(value),
                }
            )
        payload = {"slides": slides}

    if not isinstance(payload, dict):
        payload = {}

    slides = payload.get("slides")
    if not isinstance(slides, list):
        slides = []

    normalized_slides: List[Dict[str, Any]] = []
    for slide in slides:
        if isinstance(slide, dict):
            normalized_slides.append(slide)

    settings = payload.get("settings")
    if not isinstance(settings, dict):
        settings = {}

    base_settings = _base_settings(settings.get("theme") or fallback_theme)
    merged_settings = {**base_settings, **settings}
    if "palette" not in merged_settings:
        merged_settings["palette"] = resolve_theme(merged_settings.get("theme"))

    return {"slides": normalized_slides, "settings": merged_settings}


def _payload_from_outline(outline: Dict[str, Any], theme_id: str) -> Dict[str, Any]:
    slides = outline.get("slides")
    if not isinstance(slides, list):
        slides = []
    normalized: List[Dict[str, Any]] = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        normalized.append(
            {
                "layout": slide.get("layout") or "insight",
                "title": slide.get("title"),
                "subtitle": slide.get("subtitle"),
                "body": slide.get("body"),
                "bullets": slide.get("bullets") or [],
                "notes": slide.get("notes"),
            }
        )
    return {"slides": normalized, "settings": _base_settings(theme_id)}


def _slides_payload(post: Post) -> SlidesPayload:
    normalized = _normalize_payload(post.image_paths_json, post.theme)
    return SlidesPayload(**normalized)


def _post_summary(post: Post) -> PostOut:
    return PostOut(
        id=post.id,
        type=post.type,
        status=post.status,
        slides=post.slides,
        share_url=_share_url(post),
        theme=post.theme,
    )


def _post_editor(post: Post) -> PostEditorOut:
    return PostEditorOut(
        **_post_summary(post).dict(),
        source_text=post.source_text,
        data=_slides_payload(post),
    )


def _require_editor_access(post: Post, token: Optional[str]) -> None:
    if not token:
        raise HTTPException(403, "Token required")
    payload = verify_token(token)
    if not payload or payload.get("post_id") != post.id:
        raise HTTPException(403, "Invalid token")
    if post.share_token != token:
        raise HTTPException(403, "Invalid token")


@app.get("/", response_class=HTMLResponse)
def root():
    tpl = env.get_template("index.html")
    return tpl.render()


@app.post("/api/generate", response_model=GenerateOut)
def generate(req: GenerateIn):
    if req.format != "carousel":
        raise HTTPException(400, "format=carousel is the only supported format")
    if req.source.kind != "text":
        raise HTTPException(400, "Only text source is supported right now")
    topic = (req.source.text or "").strip()
    if not topic:
        raise HTTPException(400, "source.text is empty")

    try:
        outline = build_outline(text=topic, slides=req.slides or 6)
    except OutlineValidationError as exc:
        raise HTTPException(400, str(exc)) from exc

    theme_id = normalize_theme_id(req.theme)
    payload = _payload_from_outline(outline, theme_id)
    slides_count = len(payload["slides"]) or req.slides or 6

    with get_session() as session:
        post = Post(
            type=req.format,
            status="ready",
            source_kind=req.source.kind,
            source_text=topic,
            slides=slides_count,
            theme=theme_id,
            image_paths_json=json.dumps(payload, ensure_ascii=False),
        )
        session.add(post)
        session.commit()
        session.refresh(post)

        token = make_signed_token({"post_id": post.id})
        post.share_token = token
        post.share_token_used = False
        session.add(post)
        session.commit()

        return GenerateOut(
            post_id=post.id,
            status=post.status,
            share_url=_share_url(post),
            token=token,
        )


@app.get("/api/posts/{post_id}", response_model=PostOut)
def get_post(post_id: int):
    with get_session() as session:
        post = session.get(Post, post_id)
        if not post:
            raise HTTPException(404, "Not found")
        return _post_summary(post)


@app.get("/api/posts/{post_id}/editor", response_model=PostEditorOut)
def get_post_editor(post_id: int, token: str = Query(..., description="Share token")):
    with get_session() as session:
        post = session.get(Post, post_id)
        if not post:
            raise HTTPException(404, "Not found")
        _require_editor_access(post, token)
        return _post_editor(post)


@app.patch("/api/posts/{post_id}", response_model=PostEditorOut)
def update_post(
    post_id: int,
    req: PostUpdateIn,
    token: str = Query(..., description="Share token"),
):
    with get_session() as session:
        post = session.get(Post, post_id)
        if not post:
            raise HTTPException(404, "Not found")
        _require_editor_access(post, token)

        payload = _normalize_payload(post.image_paths_json, post.theme)

        if req.slides is not None:
            payload["slides"] = [slide.dict(exclude_none=True) for slide in req.slides]
            post.slides = len(payload["slides"])

        if req.settings is not None:
            payload["settings"].update(req.settings)

        if req.theme:
            theme_id = normalize_theme_id(req.theme)
            post.theme = theme_id
            payload["settings"]["theme"] = theme_id
            payload["settings"]["palette"] = resolve_theme(theme_id)

        post.image_paths_json = json.dumps(payload, ensure_ascii=False)
        post.status = "ready"
        session.add(post)
        session.commit()
        session.refresh(post)
        return _post_editor(post)


@app.post("/api/posts/{post_id}/background-image", response_model=BackgroundUploadOut)
async def upload_background_asset(
    post_id: int,
    token: str = Query(..., description="Share token"),
    file: UploadFile = File(...),
):
    with get_session() as session:
        post = session.get(Post, post_id)
        if not post:
            raise HTTPException(404, "Not found")
        _require_editor_access(post, token)
        payload = _normalize_payload(post.image_paths_json, post.theme)

        content_type = (file.content_type or "").lower()
        if content_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise HTTPException(400, "Unsupported file type")
        data = await file.read()
        if len(data) > 8 * 1024 * 1024:
            raise HTTPException(400, "File too large (max 8MB)")

        try:
            url = save_background_image(post_id, file.filename or "background.png", data)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        settings = payload.setdefault("settings", {})
        library = settings.setdefault(
            "backgroundLibrary",
            {
                "colors": [],
                "gradients": [],
                "images": [],
            },
        )
        images = library.setdefault("images", [])
        if url not in images:
            images.append(url)

        settings["background"] = settings.get("background") or _default_background(
            settings.get("palette") or resolve_theme(post.theme or DEFAULT_THEME)
        )
        settings["background"]["type"] = "image"
        settings["background"]["imageUrl"] = url

        post.image_paths_json = json.dumps(payload, ensure_ascii=False)
        post.status = "ready"
        session.add(post)
        session.commit()
        return BackgroundUploadOut(url=url)


@app.get("/posts/{post_id}/editor", response_class=HTMLResponse)
def editor_page(post_id: int, token: str):
    with get_session() as session:
        post = session.get(Post, post_id)
        if not post or post.status != "ready":
            raise HTTPException(404, "Post not ready")
        _require_editor_access(post, token)

    tpl = env.get_template("editor_shell.html")
    return tpl.render(post_id=post_id, token=token)


@app.post("/api/posts/{post_id}/export", response_model=ExportOut)
def export_post(post_id: int, req: ExportIn, token: str = Query(..., description="Share token")):
    with get_session() as session:
        post = session.get(Post, post_id)
        if not post:
            raise HTTPException(404, "Not found")
        _require_editor_access(post, token)

    # Placeholder implementation; actual rendering pipeline TBD
    return ExportOut(
        status="not_implemented",
        detail=f"Export of type {req.format.upper()} for range {req.range} is not available yet.",
    )


def _apply_ai_action(action: str, value: str) -> str:
    base = (value or "").strip()
    if not base:
        return "..."
    if action == "shorten":
        half = max(len(base) // 2, 1)
        return base[:half].rstrip() + "..."
    if action == "expand":
        return f"{base}\n\nДополнение: {base}"
    if action == "simplify":
        sentences = base.split(".")
        return sentences[0].strip() + "."
    if action == "tone_friendly":
        return f"👋 Привет! {base}"
    if action == "tone_professional":
        return f"Уважаемые коллеги, {base}"
    if action == "translate_ru":
        return f"Перевод на русский: {base}"
    if action == "translate_en":
        return f"English translation: {base}"
    # improve / default
    return f"{base} (улучшено)"


@app.post("/api/posts/{post_id}/ai", response_model=AIActionOut)
def ai_action(
    post_id: int,
    req: AIActionIn,
    token: str = Query(..., description="Share token"),
):
    with get_session() as session:
        post = session.get(Post, post_id)
        if not post:
            raise HTTPException(404, "Not found")
        _require_editor_access(post, token)

    allowed_fields = {"title", "subtitle", "body", "cta"}
    if req.field not in allowed_fields:
        raise HTTPException(400, "Unsupported field")

    new_value = _apply_ai_action(req.action, req.value)
    return AIActionOut(field=req.field, action=req.action, value=new_value)
