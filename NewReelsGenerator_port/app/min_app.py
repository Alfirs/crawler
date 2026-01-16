import os
from app.env_loader import load_env

# Определяем корень проекта (на уровень выше от app/)
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(ROOT_DIR, ".env")
env_vars = load_env(ENV_PATH)

from fastapi import FastAPI, Form
from fastapi.staticfiles import StaticFiles
import sys

from app.routes.ui_carousel import router as ui_carousel_router
from app.services.image_gen import get_selected_model

# Проверяем загрузку API ключа после load_env()
api_key = os.getenv("NEUROAPI_API_KEY")
if not api_key:
    print("[min_app] WARNING: NEUROAPI_API_KEY not found in environment after load_env()")
    print(f"[min_app] DEBUG: env_vars from file: {list(env_vars.keys())}")
else:
    api_key_short = api_key[:8] + "..." if len(api_key) > 8 else api_key
    print(f"[min_app] Loaded API key: {api_key_short}")

# Дополнительная проверка базового URL
base_url = os.getenv("NEUROAPI_BASE_URL")
if base_url:
    print(f"[min_app] Base URL: {base_url}")
else:
    print("[min_app] WARNING: NEUROAPI_BASE_URL not found")

# Прогрев модели при старте (без сетевого пробинга)
try:
    model = get_selected_model()
    print(f"[NeuroAPI] model at startup: {model}")
except Exception as e:
    print("[NeuroAPI] model warmup skipped:", e)

app = FastAPI(title="Carousel Mini Server")

# раздача /static и /output
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/output", StaticFiles(directory="output"), name="output")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# роутер с формой и генерацией
app.include_router(ui_carousel_router)

@app.get("/", include_in_schema=False)
def root():
    return {"ok": True, "info": "Open /carousel for UI"}


@app.post("/batch")
def batch_generate_api(
    template: str = Form(...),
    topic: str = Form(...),
    count: int = Form(5),
):
    from app.services.batch_generate import batch_generate

    batches = batch_generate(template, topic, count)
    return {"ok": True, "batches": batches}
