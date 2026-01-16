import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from generator.generate_full_carousel import generate_slides

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Carousel Generator (GPT-image-1)")

app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def list_outputs() -> List[str]:
    files = sorted([f.name for f in OUTPUT_DIR.glob("slide_*.jpg")])
    return files


@app.get("/api/files")
async def api_files():
    return JSONResponse(list_outputs())


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "message": None,
            "files": list_outputs(),
            "running": False,
            "now": __import__("time").time(),
        },
    )


def _run_generate(topic: str, slides: int, username: str, style_seed: Optional[int]) -> None:
    try:
        meta = generate_slides(topic=topic, slides=slides, username=username, style_seed=style_seed, parallel=2)
        payload = {"generated_at": datetime.utcnow().isoformat(), "files": meta}
        (OUTPUT_DIR / "last_meta.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        error_payload = {"timestamp": datetime.utcnow().isoformat(), "error": str(e)}
        (OUTPUT_DIR / "last_error.json").write_text(json.dumps(error_payload, ensure_ascii=False, indent=2), encoding="utf-8")


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    background_tasks: BackgroundTasks,
    topic: str = Form(...),
    slides: int = Form(...),
    username: str = Form(...),
    style_seed: Optional[str] = Form(None),
):
    seed_val: Optional[int] = None
    if style_seed:
        try:
            seed_val = int(style_seed)
        except Exception:
            seed_val = None

    background_tasks.add_task(_run_generate, topic, slides, username, seed_val)

    return TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "message": f"⏳ Генерация {slides} слайдов по теме «{topic}» запущена. Обнови страницу через 20–40 сек.",
            "files": list_outputs(),
            "running": True,
            "now": __import__("time").time(),
        },
    )
