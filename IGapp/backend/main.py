# backend/main.py
import os
import re
import sys
import json
import uuid
import shutil
import subprocess
from typing import List, Optional, Tuple
import unicodedata
import textwrap

import requests
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
)
from pydantic import BaseModel

from .jobs import JobManager
from .renderer import render_reels  # render_reels принимает **overlay_kwargs

# -------------------- env/dirs --------------------
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BASE_DIR = os.path.dirname(__file__)
UPLOADS = os.path.join(BASE_DIR, "storage", "uploads")
OUTPUTS = os.path.join(BASE_DIR, "storage", "outputs")
os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(OUTPUTS, exist_ok=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# дефолтная «сетка» — Qwen free
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-7b-instruct:free")
# отдельная модель для генерации текстов (можно переопределить в .env)
OPENROUTER_MODEL_CAPTION = os.getenv("OPENROUTER_MODEL_CAPTION", OPENROUTER_MODEL)

# -------------------- app -------------------------
app = FastAPI(title="AutoReels API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # локально ок
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = JobManager(max_workers=1)

# -------------------- utils -----------------------
def _exec(cmd: str) -> Tuple[int, str]:
    print("FFMPEG:", cmd)
    proc = subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    return proc.returncode, proc.stdout

def _run_with_fallback(base_cmd: str, vf_str: str) -> str:
    """
    Пытаемся прогнать ffmpeg. Если упал — по очереди убираем подозрительные фильтры:
    1) deshake
    2) drawtext (полностью)
    Возвращаем stdout успешного запуска либо поднимаем 500 с логом последней ошибки.
    """
    # 0) как есть
    rc, out = _exec(base_cmd)
    if rc == 0:
        return out
    print("\n--- ffmpeg failed; output ---\n", out, "\n-----------------------------\n")

    # 1) убираем deshake, если был
    if "deshake" in vf_str:
        vf_no_deshake = ",".join([f for f in vf_str.split(",") if f.strip() != "deshake"]) or "null"
        cmd1 = base_cmd.replace(f'-vf "{vf_str}"', f'-vf "{vf_no_deshake}"')
        rc, out2 = _exec(cmd1)
        if rc == 0:
            print("FFMPEG: succeeded after removing deshake")
            return out2
        print("\n--- still failing (no deshake); output ---\n", out2, "\n-----------------------------------------\n")
        vf_str = vf_no_deshake  # продолжаем с этим

    # 2) убираем drawtext полностью
    if "drawtext=" in vf_str:
        parts = [p for p in vf_str.split(",") if not p.strip().startswith("drawtext=")]
        vf_no_text = ",".join(parts) or "null"
        cmd2 = base_cmd.replace(f'-vf "{vf_str}"', f'-vf "{vf_no_text}"')
        rc, out3 = _exec(cmd2)
        if rc == 0:
            print("FFMPEG: succeeded after removing drawtext")
            return out3
        print("\n--- still failing (no drawtext); output ---\n", out3, "\n-------------------------------------------\n")

    raise HTTPException(500, out)

def _write_textfile(text: str) -> str:
    """Пишем текст в UTF-8 файл для drawtext=textfile=... (надёжно для переводов строки/emoji/кириллицы)."""
    import tempfile
    tmpdir = os.path.join(UPLOADS, "_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="txt_", suffix=".txt", dir=tmpdir)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text or "")
    return path.replace("\\", "/")  # ffmpeg на Windows любит прямые слеши

def _ff_path(p: str) -> str:
    """Нормализуем путь под ffmpeg: слеши вперёд, двоеточия экранируем."""
    return (p or "").replace("\\", "/").replace(":", r"\:")

def _default_fontfile() -> Optional[str]:
    """Подбираем системный .ttf для drawtext, чтобы не падать на Windows."""
    if os.name == "nt":  # Windows
        candidates = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\ARIAL.TTF",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\SEGOEUI.TTF",
        ]
    elif sys.platform == "darwin":  # macOS
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:  # Linux
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def _probe_video_wh(path: str) -> Tuple[Optional[int], Optional[int]]:
    """Через ffprobe достаём ширину/высоту исходника."""
    try:
        cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "{path}"'
        rc, out = _exec(cmd)
        if rc == 0 and "x" in out.strip():
            w_s, h_s = out.strip().split("x")
            return int(w_s), int(h_s)
    except Exception:
        pass
    return None, None

def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

# ---------- wrap текст для двух строк ----------
def wrap_text_for_width(s: str, font_size: int, w_coeff: float, max_width_pct=0.88, max_lines=2):
    # эмпирическая ширина символа для гротесков
    avg_char_w = font_size * 0.55
    max_line_px = int(w_coeff * max_width_pct)
    max_chars = max(8, int(max_line_px / avg_char_w))

    words = (s or "").split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if len(test) <= max_chars:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)

    # усечение последней строки с многоточием
    if lines and len(lines[-1]) > max_chars:
        lines[-1] = lines[-1][:max(0, max_chars - 1)] + "…"
    return "\n".join(lines)

# ==================== HEALTH ======================
@app.get("/health")
def health():
    return {"ok": True}

# ==================== UPLOAD ======================
@app.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
    saved = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1] or ""
        key = f"{uuid.uuid4().hex}{ext}"
        dst = os.path.join(UPLOADS, key)
        with open(dst, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append({"key": key, "path": dst})
    return {"files": saved}

# ============ RENDER (Reels с текстом) ============
class TemplateParams(BaseModel):
    title: Optional[str] = None
    font_file: Optional[str] = None
    font_size: int = 72
    font_color: str = "white"
    x: Optional[str] = None
    y: Optional[str] = None
    box: bool = True
    box_color: str = "black@0.45"
    boxborderw: int = 18
    shadow: bool = True
    shadow_color: str = "black"
    shadow_x: int = 2
    shadow_y: int = 2

class RenderRequest(BaseModel):
    input_keys: List[str]
    music_key: Optional[str] = None
    title: Optional[str] = None
    template: Optional[TemplateParams] = None

@app.post("/render/reels")
def render_start(body: RenderRequest):
    inputs = [os.path.join(UPLOADS, k) for k in body.input_keys]
    for p in inputs:
        if not os.path.exists(p):
            raise HTTPException(400, f"missing input {p}")
    music = os.path.join(UPLOADS, body.music_key) if body.music_key else None
    if music and not os.path.exists(music):
        raise HTTPException(400, f"missing music {music}")

    overlay_kwargs = {}
    if body.template:
        t = body.template
        font_file = t.font_file
        if font_file and not os.path.isabs(font_file):
            font_file = os.path.join(BASE_DIR, "fonts", font_file)
        overlay_kwargs = {
            "font_file": font_file,
            "font_size": t.font_size,
            "font_color": t.font_color,
            "x": t.x,
            "y": t.y,
            "box": t.box,
            "box_color": t.box_color,
            "boxborderw": t.boxborderw,
            "shadow": t.shadow,
            "shadow_color": t.shadow_color,
            "shadow_x": t.shadow_x,
            "shadow_y": t.shadow_y,
        }

    final_title = body.title or (body.template.title if body.template else None)

    job_id = jobs.submit(
        render_reels,
        inputs=inputs,
        music=music,
        title=final_title,
        out_dir=OUTPUTS,
        **overlay_kwargs,
    )
    return {"job_id": job_id}

@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    data = jobs.get(job_id)
    if not data:
        raise HTTPException(404, "job not found")
    return data

@app.get("/outputs/{job_id}.mp4")
def get_output(job_id: str):
    path = os.path.join(OUTPUTS, f"{job_id}.mp4")
    if not os.path.exists(path):
        raise HTTPException(404, "output not found")
    return FileResponse(path, media_type="video/mp4", filename=f"{job_id}.mp4")

# ==================== UI (PWA) ====================
@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AutoReels UI</title>
<link rel="manifest" href="/manifest.json"><link rel="icon" href="https://via.placeholder.com/192.png?text=AR"><meta name="theme-color" content="#111111">
<script> if('serviceWorker' in navigator){ navigator.serviceWorker.register('/sw.js').catch(console.error) } </script>
<style>
 body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;max-width:720px;margin:0 auto;padding:16px}
 h1{font-size:20px;margin:0 0 12px}.card{border:1px solid #ddd;border-radius:10px;padding:14px;margin:10px 0}
 label{display:block;margin:10px 0 6px} input[type="text"], textarea{width:100%;padding:10px;border:1px solid #ccc;border-radius:8px}
 button{padding:10px 14px;border:0;border-radius:8px;background:#111;color:#fff} #log{white-space:pre-wrap;background:#fafafa;border:1px dashed #ddd;border-radius:8px;padding:10px;margin-top:10px}
 progress{width:100%} a.btn{display:inline-block;margin-top:10px} pre#tpl{background:#f6f6f6;border:1px dashed #ddd;border-radius:8px;padding:10px;display:none}
</style>
<body>
  <h1>AutoReels — простой UI (PWA)</h1>

  <div class="card">
    <label>Видео для умного редактирования (1 файл)</label>
    <input id="smartVideo" type="file" accept="video/*">
    <label>Промпт (например: «кинематографично, стабилизация, белый жирный текст сверху по центру: "Секретный лайфхак"»)</label>
    <textarea id="smartPrompt" rows="3"></textarea>
    <div style="margin-top:12px;display:flex;gap:8px">
      <button id="smartBtn">AI смарт-редактирование</button>
    </div>
    <div id="smartStatus" style="margin-top:12px"></div>
    <div id="smartLog" style="white-space:pre-wrap;margin-top:8px"></div>
  </div>

  <div class="card">
    <label>Выбери видео (1–30 шт.)</label>
    <input id="videos" type="file" accept="video/*" multiple>
    <label>Музыка (опционально)</label>
    <input id="music" type="file" accept="audio/*,video/*">
    <label>Заголовок (опционально)</label>
    <input id="title" type="text" placeholder="Текст поверх видео">
    <label>Промпт оформления (для автолэйаута)</label>
    <textarea id="prompt" rows="3" placeholder="жирный Montserrat, сверху по центру, белый текст, чёрная подложка, тень"></textarea>
    <pre id="tpl"></pre>
    <div style="margin-top:12px;display:flex;gap:8px">
      <button id="start">Собрать Reels</button>
      <button id="reset" style="background:#666">Сброс</button>
    </div>
    <div id="status" style="margin-top:12px"></div>
    <progress id="prog" max="100" value="0" style="display:none"></progress>
    <div id="log"></div>
  </div>

<script>
const $ = s => document.querySelector(s);
function log(t){ const el=$('#log'); el.textContent = (el.textContent? el.textContent+"\\n":"")+t; }
function slog(t){ const el=$('#smartLog'); el.textContent = (el.textContent? el.textContent+"\\n":"")+t; }

async function uploadFiles(files){
  const fd = new FormData();
  for (const f of files) fd.append('files', f);
  const r = await fetch('/upload', { method:'POST', body: fd });
  if(!r.ok) throw new Error('upload failed');
  return (await r.json()).files;
}

async function poll(jobId){
  $('#prog').style.display='block';
  while(true){
    const r = await fetch('/jobs/'+jobId);
    const st = await r.json();
    $('#status').textContent = 'Статус: ' + st.status + ' (' + st.progress + '%)';
    $('#prog').value = st.progress || 0;
    if(st.status === 'done'){
      const a = document.createElement('a');
      a.href = '/outputs/'+jobId+'.mp4'; a.textContent = 'Скачать результат';
      a.className = 'btn'; a.download = jobId+'.mp4';
      $('#status').appendChild(document.createElement('br')); $('#status').appendChild(a);
      break;
    }
    if(st.status === 'error'){ log('Ошибка: ' + (st.error || 'Unknown')); break; }
    await new Promise(r => setTimeout(r, 1500));
  }
}

$('#reset').onclick = ()=>{
  ['videos','music','title','prompt'].forEach(id=>{ const el=$('#'+id); if(el) el.value=''; });
  $('#status').textContent=''; $('#log').textContent=''; $('#tpl').style.display='none';
  $('#prog').style.display='none'; $('#prog').value=0;
};

$('#start').onclick = async ()=>{
  try{
    $('#log').textContent = '';
    const vids = Array.from($('#videos').files || []);
    if(vids.length === 0){ alert('Выбери хотя бы одно видео'); return; }
    if(vids.length > 30){ alert('Максимум 30 видео'); return; }
    log('Загружаю видео ('+vids.length+') …');
    const upV = await uploadFiles(vids);

    let musicKey = null;
    const mus = $('#music').files?.[0];
    if(mus){
      log('Загружаю музыку …');
      const upM = await uploadFiles([mus]);
      musicKey = upM[0].key;
    }

    const input_keys = upV.map(x=>x.key);
    const prompt = ($('#prompt').value || '').trim();
    let template = null;

    if (prompt) {
      log('Запрашиваю оформление у AI …');
      const lr = await fetch('/ai/layout', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ prompt })
      });
      if(!lr.ok){ throw new Error('ai layout failed'); }
      template = await lr.json();
      const pretty = JSON.stringify(template, null, 2);
      const tplEl = document.getElementById('tpl'); tplEl.style.display = 'block'; tplEl.textContent = pretty;
    }

    const title = $('#title').value || (template && template.title) || null;

    log('Стартую рендер …');
    const r = await fetch('/render/reels', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ input_keys, music_key: musicKey, title, template })
    });
    if(!r.ok) throw new Error('render start failed');
    const {job_id} = await r.json();
    log('Задача: '+job_id);
    await poll(job_id);
  }catch(e){ log('Ошибка: '+e.message); }
};

// === Новый смарт-эндпоинт ===
$('#smartBtn').onclick = async ()=>{
  try{
    $('#smartLog').textContent=''; $('#smartStatus').textContent='';
    const f = $('#smartVideo').files?.[0];
    if(!f){ alert('Выбери видео'); return; }
    const form = new FormData();
    form.append('file', f);
    form.append('prompt', ($('#smartPrompt').value||'').trim());

    const r = await fetch('/ai/edit-video-smart', { method:'POST', body: form });
    if(!r.ok) throw new Error('smart edit failed');
    const data = await r.json();
    $('#smartStatus').innerHTML = '<a class="btn" href="'+data.url+'" download>Скачать результат</a>';
    if(data.plan){ slog('План правок:\\n'+JSON.stringify(data.plan, null, 2)); }
    if(data.overlay_dbg){ slog('Overlay debug:\\n'+JSON.stringify(data.overlay_dbg, null, 2)); }
  }catch(e){ slog('Ошибка: '+e.message); }
};
</script>
</body></html>
"""

@app.get("/manifest.json")
def manifest():
    return JSONResponse({
        "name": "AutoReels",
        "short_name": "AutoReels",
        "start_url": "/ui",
        "display": "standalone",
        "background_color": "#111111",
        "theme_color": "#111111",
        "icons": [
            {"src": "https://via.placeholder.com/192.png?text=AR", "sizes": "192x192", "type": "image/png"},
            {"src": "https://via.placeholder.com/512.png?text=AR", "sizes": "512x512", "type": "image/png"}
        ]
    })

@app.get("/sw.js")
def sw():
    js = (
        "self.addEventListener('install', e => { self.skipWaiting(); });\n"
        "self.addEventListener('activate', e => { self.clients.claim(); });\n"
        "self.addEventListener('fetch', e => {});\n"
    )
    return PlainTextResponse(js, media_type="application/javascript")

# =============== AI layout (для Reels) ===============
def fallback_layout(prompt: str) -> dict:
    prompt_l = (prompt or "").lower()
    font_color = "white"; box_color = "black@0.45"; x = "(w-text_w)/2"; y = "h*0.12"
    if any(k in prompt_l for k in ["низ","снизу","bottom"]): y = "h*0.78"
    if any(k in prompt_l for k in ["центр","center"]): y = "(h-text_h)/2"
    font_size = 72
    if any(k in prompt_l for k in ["крупн","big","huge","xl"]): font_size = 96
    if any(k in prompt_l for k in ["маленьк","small","xs"]): font_size = 48
    if "красн" in prompt_l or "red" in prompt_l: font_color = "red"
    if "жёлт" in prompt_l or "желт" in prompt_l or "yellow" in prompt_l: font_color = "yellow"
    if "чёрн" in prompt_l or "черн" in prompt_l or "black" in prompt_l:
        font_color, box_color = "black", "white@0.55"
    return {
        "title": prompt or "Трендовый заголовок",
        "font_file": None, "font_size": font_size, "font_color": font_color,
        "x": x, "y": y, "box": True, "box_color": box_color, "boxborderw": 18,
        "shadow": True, "shadow_color": "black", "shadow_x": 2, "shadow_y": 2,
    }

class LayoutRequest(BaseModel):
    prompt: str
    video_width: int = 1080
    video_height: int = 1920
    prefer_font: Optional[str] = "Montserrat-SemiBold.ttf"
    locale: str = "ru"

@app.post("/ai/layout")
def ai_layout(body: LayoutRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", OPENROUTER_MODEL)
    if not api_key:
        return fallback_layout(body.prompt)

    system_msg = (
        "Ты ассистент по дизайну коротких вертикальных видео (Reels, 1080x1920). "
        "Верни ЧИСТЫЙ JSON: {title, font_file(optional), font_size, font_color, x, y, "
        "box, box_color, boxborderw, shadow, shadow_color, shadow_x, shadow_y}. "
        "x/y — выражения ffmpeg ((w-text_w)/2, h*0.12 и т.п.). По умолчанию: белый текст, тёмная подложка, тень."
    )
    user_msg = (
        f"Видео {body.video_width}x{body.video_height}. Если можно — шрифт '{body.prefer_font}'. "
        f"Пожелания: {body.prompt}"
    )
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages":[{"role":"system","content":system_msg},{"role":"user","content":user_msg}],
                "temperature":0.3
            },
            timeout=60,
        )
        if r.status_code >= 400:
            print("OpenRouter error:", r.status_code, r.text[:400])
            return fallback_layout(body.prompt)
        text = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            print("AI layout no JSON:", text[:400])
            return fallback_layout(body.prompt)
        data = json.loads(m.group(0))
        ff = data.get("font_file")
        if ff and not os.path.isabs(ff):
            data["font_file"] = os.path.join(BASE_DIR, "fonts", ff)
        return data
    except Exception as e:
        print("OpenRouter exception:", repr(e))
        return fallback_layout(body.prompt)

@app.get("/debug/openrouter")
def debug_openrouter():
    return {"has_key": bool(os.getenv("OPENROUTER_API_KEY")), "model": os.getenv("OPENROUTER_MODEL")}

# =========== AI smart edit (ИИ план → ffmpeg) ==========
async def llm_complete(messages, model=None, temperature=0.5, max_tokens=500):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise HTTPException(500, "OPENROUTER_API_KEY missing")
    model = model or os.getenv("OPENROUTER_MODEL", OPENROUTER_MODEL)
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "AutoReels",
    }
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        if r.status_code != 200:
            raise HTTPException(500, f"OpenRouter error: {r.text[:400]}")
        return r.json()["choices"][0]["message"]["content"]

def _json_only(s: str) -> dict:
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s.replace("json", "", 1).strip()
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        raise ValueError("no JSON in LLM reply")
    return json.loads(m.group(0))

# --- разговорный парсер
_CAPTION_KEYS = ["подпись", "надпись", "заголовок", "тайтл", "title", "caption", "описан", "текст"]

def _extract_overlay_from_prompt(prompt: str):
    """Пытаемся достать текст, регион, выравнивание и настроение фильтра из разговорной фразы."""
    p = (prompt or "").strip()
    pl = p.lower()

    # region
    region = "middle"
    if "сверху" in pl or "верх" in pl or "top" in pl:
        region = "top"
    elif "снизу" in pl or "низ" in pl or "bottom" in pl:
        region = "bottom"
    elif "по центру" in pl or "центр" in pl or "middle" in pl:
        region = "middle"

    # align
    align = "center"
    if "слева" in pl or "left" in pl:
        align = "left"
    elif "справа" in pl or "right" in pl:
        align = "right"
    elif "по центру" in pl or "центр" in pl or "middle" in pl:
        align = "center"

    # grade hint
    grade = None
    if any(k in pl for k in ["кино", "кинематограф", "cinema", "cinematic"]):
        grade = "cinematic"
    elif any(k in pl for k in ["ярк", "прикольн", "красив", "сочно", "вкусно", "vivid", "навали цвета"]):
        grade = "vivid"
    elif "тёпл" in pl or "тепл" in pl or "warm" in pl:
        grade = "warm"
    elif "холод" in pl or "cool" in pl:
        grade = "cool"
    elif "ч/б" in pl or "черно-бел" in pl or "монохром" in pl or "bw" in pl:
        grade = "bw"

    # текст в кавычках
    text = None
    m = re.search(r"[\"“”«](.*?)[\"”»]", p)
    if m and m.group(1).strip():
        text = m.group(1).strip()
    else:
        # после слов типа «подпись/заголовок/…»
        for key in _CAPTION_KEYS:
            if key in pl:
                idx = pl.find(key)
                tail = p[idx + len(key):].strip(" :—-")
                tail = re.sub(r"(по центру|сверху|снизу|слева|справа|top|bottom|middle|left|right)", "", tail, flags=re.I)
                cand = re.split(r"[.\n]", tail, 1)[0].strip()
                if cand:
                    text = cand
                    break

    if text:
        text = unicodedata.normalize("NFKC", text).strip()

    return {"region": region, "align": align, "grade": grade, "text": text}

async def _gen_headline_from_llm(prompt: str) -> Optional[str]:
    """Просим модель придумать короткую подпись 2–5 слов, если юзер просит «подпись/описание», но текста нет."""
    sysmsg = (
        "Ты копирайтер для коротких видео. Верни ТОЛЬКО короткий заголовок (2–5 слов), "
        "на русском, без кавычек, эмодзи и хештегов."
    )
    usermsg = f"Сгенерируй подпись по запросу: {prompt}"
    try:
        txt = await llm_complete(
            [{"role": "system", "content": sysmsg}, {"role": "user", "content": usermsg}],
            temperature=0.7, max_tokens=40
        )
        line = (txt or "").strip().split("\n")[0].strip().strip('"“”«»')
        return line[:50] if line else None
    except Exception:
        return None

async def plan_from_prompt(prompt: str) -> dict:
    """Готовим план видео-редакта (цвет/стаб/текст/позиция) из разговорной фразы."""
    hints = _extract_overlay_from_prompt(prompt or "")

    system = textwrap.dedent("""
        Ты видеоредактор. Верни ЧИСТЫЙ JSON с полями:
        {
          intent: 'visual_edit'|'captions'|'both',
          color_grade: 'auto'|'cinematic'|'vivid'|'warm'|'cool'|'bw'|null,
          stabilize: bool, sharpen: bool, denoise: bool,
          speed: number|null, vignette: bool,
          text_overlay: {
            text, font_file(null|name.ttf), font_size, font_color, box,
            box_color, boxborderw, shadow, shadow_color, shadow_x, shadow_y,
            region:'top'|'middle'|'bottom', align:'left'|'center'|'right',
            safe_top, safe_bottom, safe_side, margin_x, margin_y
          },
          captions: { title, description, hashtags[] }
        }
        Правила: если пользователь говорит «сделай красиво/прикольный фильтр» — выбери 'vivid'.
        Если «кино/кинематографично» — 'cinematic'. Если просит «по центру/сверху/снизу/слева/справа» — проставь region/align.
        Если явного текста нет, оставь text_overlay.text пустым — текст сгенерируем отдельно.
        По умолчанию safe_top=0.12, safe_bottom=0.12, safe_side=0.06, margin_x=24, margin_y=24.
    """).strip()

    user = f"Промпт пользователя: {prompt}\nПодсказки парсера: region={hints['region']}, align={hints['align']}, grade={hints['grade']}, text={hints['text']}"

    data = {}
    try:
        raw = await llm_complete(
            [{"role":"system","content":system},{"role":"user","content":user}],
            temperature=0.35, max_tokens=700
        )
        data = _json_only(raw)
    except Exception:
        pass

    # Итоговые значения + дефолты
    color_grade = (data.get("color_grade") if isinstance(data, dict) else None) or hints["grade"] or "vivid"
    to = (data.get("text_overlay") if isinstance(data, dict) else None) or {}

    # Определяем текст: юзер → LLM headline (если просил подпись) → fallback
    text = to.get("text") or hints["text"]
    if not text and any(k in (prompt or "").lower() for k in _CAPTION_KEYS):
        text = await _gen_headline_from_llm(prompt or "")
    if not text:
        text = (prompt or "Reels")[:60]

    region = (to.get("region") or hints["region"] or "middle").lower()
    if region not in ("top","middle","bottom"):
        region = "middle"

    align = (to.get("align") or hints["align"] or "center").lower()
    if align not in ("left","center","right"):
        align = "center"

    merged = {
        "intent": (data.get("intent") if isinstance(data, dict) else None) or "visual_edit",
        "color_grade": color_grade,
        "stabilize": bool((data.get("stabilize") if isinstance(data, dict) else True) if data else True),
        "sharpen": bool((data.get("sharpen") if isinstance(data, dict) else True) if data else True),
        "denoise": bool((data.get("denoise") if isinstance(data, dict) else False) if data else False),
        "speed": (data.get("speed") if isinstance(data, dict) else None) if data else None,
        "vignette": bool((data.get("vignette") if isinstance(data, dict) else False) if data else False),
        "text_overlay": {
            "text": text,
            "font_file": to.get("font_file"),
            "font_size": int(to.get("font_size") or 0),  # 0 => авторазмер ниже
            "font_color": to.get("font_color") or "white",
            "box": bool(to.get("box", True)),
            "box_color": to.get("box_color") or "black@0.45",
            "boxborderw": int(to.get("boxborderw") or 18),
            "shadow": bool(to.get("shadow", True)),
            "shadow_color": to.get("shadow_color") or "black",
            "shadow_x": int(to.get("shadow_x") or 2),
            "shadow_y": int(to.get("shadow_y") or 2),
            "region": region,
            "align": align,
            "safe_top": float(to.get("safe_top", 0.12)),
            "safe_bottom": float(to.get("safe_bottom", 0.12)),
            "safe_side": float(to.get("safe_side", 0.06)),
            "margin_x": int(to.get("margin_x", 24)),
            "margin_y": int(to.get("margin_y", 24)),
        },
        "captions": data.get("captions") or {
            "title": text,
            "description": prompt,
            "hashtags": ["reels","video","ai"]
        }
    }
    return merged

def _xy_with_safe(region: str, align: str, w_expr="w", h_expr="h", text_w="text_w", text_h="text_h",
                  safe_top=0.12, safe_bottom=0.12, safe_side=0.06, margin_x=24, margin_y=24):
    # X
    if align == "left":
        x = f"({w_expr}*{safe_side})+{margin_x}"
    elif align == "right":
        x = f"({w_expr}*(1-{safe_side}))-{text_w}-{margin_x}"
    else:
        x = f"({w_expr}-{text_w})/2"

    # Y
    if region == "top":
        y = f"({h_expr}*{safe_top})+{margin_y}"
    elif region == "bottom":
        y = f"({h_expr}*(1-{safe_bottom}))-{text_h}-{margin_y}"
    else:
        y = f"({h_expr}-{text_h})/2"

    return x, y


@app.post("/ai/edit-video-smart")
async def ai_edit_video_smart(
    file: UploadFile = File(...),
    prompt: str = Form(""),
):
    # 1) сохраняем исходник
    ext = os.path.splitext(file.filename or "")[1] or ".mp4"
    src_key = f"{uuid.uuid4().hex}{ext}"
    src_path = os.path.join(UPLOADS, src_key)
    with open(src_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    # размеры видео (для авторазмера и переносов)
    vid_w, vid_h = _probe_video_wh(src_path)
    # 2) план правок от LLM
    plan = await plan_from_prompt(prompt or "")
    vf, af = [], []

    # цвет/тон
    grade = (plan.get("color_grade") or "auto").lower()
    if grade == "cinematic":
        vf += ["eq=contrast=1.08:brightness=0.01:saturation=1.05", "colorbalance=rs=.01:gs=.0:bs=-.01"]
    elif grade == "vivid":
        vf += ["eq=contrast=1.05:saturation=1.25"]
    elif grade == "warm":
        vf += ["colorbalance=rs=.02:gs=.01:bs=-.01"]
    elif grade == "cool":
        vf += ["colorbalance=rs=-.01:gs=.0:bs=.02"]
    elif grade == "bw":
        vf += ["hue=s=0"]

    # стаб/шарп/шум
    if plan.get("stabilize"): vf.append("deshake")
    if plan.get("sharpen"):   vf.append("unsharp=5:5:0.6:5:5:0.6")
    if plan.get("denoise"):   vf.append("hqdn3d=1.0:1.0:6:6")

    # виньетка
    if plan.get("vignette"):  vf.append("vignette=PI/5")

    # скорость
    spd = plan.get("speed")
    if isinstance(spd, (int,float)) and spd and spd > 0 and abs(spd-1.0) > 1e-3:
        scale = 1.0/float(spd)
        vf.append(f"setpts={scale}*PTS")
        tempo = float(spd)
        if tempo < 0.5: tempo = 0.5
        if tempo > 2.0:
            parts=[]; t=tempo
            while t>2.0: parts.append(2.0); t/=2.0
            parts.append(t)
            for p in parts: af.append(f"atempo={p}")
        else:
            af.append(f"atempo={tempo}")

    # текст (через textfile)
    to = plan.get("text_overlay") or {}
    text = (to.get("text") or "").rstrip()
    overlay_dbg = None

    if text:
        region = (to.get("region") or "top").lower()
        align  = (to.get("align") or "center").lower()
        safe_top    = float(to.get("safe_top", 0.12))
        safe_bottom = float(to.get("safe_bottom", 0.12))
        safe_side   = float(to.get("safe_side", 0.06))
        margin_x    = int(to.get("margin_x", 24))
        margin_y    = int(to.get("margin_y", 24))
        x, y = _xy_with_safe(region, align,
                             safe_top=safe_top, safe_bottom=safe_bottom, safe_side=safe_side,
                             margin_x=margin_x, margin_y=margin_y)

        font_file = to.get("font_file")
        if font_file and not os.path.isabs(font_file):
            cand = os.path.join(BASE_DIR, "fonts", font_file)
            font_file = cand if os.path.exists(cand) else None
        if not font_file:
            font_file = _default_fontfile()

        # авторазмер: 6% от высоты, с клампом 42..108, если font_size не задан
        font_size = int(to.get("font_size") or 0)
        if not font_size:
            if vid_h:
                font_size = _clamp(int(vid_h * 0.06), 42, 108)
            else:
                font_size = 72

        # перенос до двух строк с учётом ширины кадра
        wrapped = wrap_text_for_width(text, font_size, w_coeff=vid_w or 1080, max_width_pct=1.0 - 2*safe_side, max_lines=2)

        # ключ: нормализуем пути для ffmpeg и используем textfile
        textfile_path = _ff_path(_write_textfile(wrapped))
        fontfile_expr = f":fontfile='{_ff_path(font_file)}'" if font_file else ":font='Arial'"

        font_color  = to.get("font_color") or "white"
        box         = 1 if bool(to.get("box", True)) else 0
        box_color   = to.get("box_color") or "black@0.45"
        boxborderw  = int(to.get("boxborderw") or 18)
        shadow      = bool(to.get("shadow", True))
        shadow_col  = to.get("shadow_color") or "black"
        shadow_x    = int(to.get("shadow_x") or 2)
        shadow_y    = int(to.get("shadow_y") or 2)

        if shadow:
            vf.append(
                f"drawtext=textfile='{textfile_path}'{fontfile_expr}:"
                f"x=({x})+{shadow_x}:y=({y})+{shadow_y}:"
                f"fontsize={font_size}:fontcolor={shadow_col}:box=0"
            )
        vf.append(
            f"drawtext=textfile='{textfile_path}'{fontfile_expr}:"
            f"x={x}:y={y}:"
            f"fontsize={font_size}:fontcolor={font_color}:"
            f"box={box}:boxcolor={box_color}:boxborderw={boxborderw}"
        )

        overlay_dbg = {
            "final_text": wrapped,
            "region": region,
            "align": align,
            "font_file": font_file,
            "font_size": font_size,
            "font_color": font_color,
            "box": bool(box),
            "box_color": box_color,
            "boxborderw": boxborderw,
            "shadow": bool(shadow),
            "shadow_color": shadow_col,
            "shadow_x": shadow_x,
            "shadow_y": shadow_y,
            "safe_top": safe_top,
            "safe_bottom": safe_bottom,
            "safe_side": safe_side,
            "margin_x": margin_x,
            "margin_y": margin_y,
        }

    vf_str = ",".join(vf) if vf else "null"
    af_str = ",".join(af) if af else "anull"

    # 3) рендер (с фолбэками)
    out_key = f"{uuid.uuid4().hex}.mp4"
    out_path = os.path.join(OUTPUTS, out_key)
    cmd = (
        f'ffmpeg -hide_banner -loglevel error -y -i "{src_path}" '
        f'-vf "{vf_str}" -af "{af_str}" '
        f'-c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 192k "{out_path}"'
    )
    _run_with_fallback(cmd, vf_str)

    return {"output_key": out_key, "url": f"/outputs/{out_key}", "plan": plan, "overlay_dbg": overlay_dbg}

# ---- совместимость со старым клиентом ----
@app.post("/ai/edit-video")
async def ai_edit_video_compat(
    file: UploadFile = File(...),
    prompt: str = Form(""),
    stabilize: Optional[bool] = Form(None),
    sharpen: Optional[bool] = Form(None),
    tone: Optional[str] = Form("auto"),
):
    # всё делаем через smart
    return await ai_edit_video_smart(file=file, prompt=prompt)

# ================ edit-image (MVP) =================
@app.post("/ai/edit-image")
async def ai_edit_image(
    file: UploadFile = File(...),
    prompt: str = Form(""),
    remove_bg: bool = Form(False),
    upscale: bool = Form(False),
):
    # пока заглушка: возвращаем оригинал
    content = await file.read()
    return Response(content, media_type=file.content_type or "image/png")

# ===================== AI CAPTION =====================
SAFE_WORDS = {
    r"\b(сука|суки|с\*ка)\b": "с*ка",
    r"\b(бля|блядь|блин)\b": "бл*",
    r"\b(хер|хуй|пизда)\b": "х*й",
    r"\b(ебашу|ебу|ебать)\b": "е*у",
    r"\b(наёб|наеб)\w*\b": "на*б",
}
def soften_profanity(text: str) -> str:
    if not text:
        return text
    out = text
    for pat, repl in SAFE_WORDS.items():
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out.replace("%", "проц.")

def _split_caption_line(s: str) -> Tuple[str, str]:
    if "|||" not in s:
        parts = s.split("\n", 1)
        title = parts[0].strip()[:90]
        desc = parts[1].strip() if len(parts) > 1 else ""
        return title, desc
    t, d = s.split("|||", 1)
    return t.strip(), d.strip()

def _hashtags_from_desc(desc: str, limit: int = 10) -> list:
    text = re.sub(r"[^\w\s#]", " ", (desc or "").lower())
    words = [w for w in text.split() if len(w) > 3 and not w.startswith("#")]
    uniq = []
    for w in words:
        if w not in uniq:
            uniq.append(w)
    tags = [f"#{w}" for w in uniq[:limit]]
    base = ["#reels", "#video", "#instagood"]
    for b in base:
        if b not in tags and len(tags) < limit:
            tags.append(b)
    return tags[:limit]

class CaptionRequest(BaseModel):
    topic: str
    language: str = "ru"
    tone: Optional[str] = "нейтральный"
    mode: str = "short"  # short | long
    soften: bool = True
    platform: str = "instagram"

@app.post("/ai/caption")
async def ai_caption(body: CaptionRequest):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise HTTPException(500, "OPENROUTER_API_KEY missing")

    sys_rules_short = (
        "Ты копирайтер Reels. Сгенерируй один сильный заголовок и короткое описание "
        "(~300–600 символов). Формат вывода: <заголовок>|||<описание>. "
        "Без постороннего текста. Не дублируй заголовок в описании. Избегай прямых триггеров."
    )
    sys_rules_long = (
        "Ты русскоязычный копирайтер для коротких видео. Правила:\n"
        "- Конфликт/поляризация, интрига, фокус на риске, правдоподобие.\n"
        "- Эмоции: несоответствие ожиданий, желание признания, страх быть обманутым, недоверие, одиночество.\n"
        "- Выделяй ВАЖНЫЕ слова КАПСОМ (до 3). Начинай заглавной буквой. Не используй знак \"%\".\n"
        "- Формат отдачи: ровно одна строка '<заголовок>|||<описание>'.\n"
        "- Описание: 1850–1950 символов, минимум 300 слов, структура 1) … 2) … 3) … 4) … 5) …, затем 3 строки CTA.\n"
        "- Маскируй опасные слова. Не повторяй заголовок в описании."
    )
    sys_msg = sys_rules_long if body.mode == "long" else sys_rules_short

    user_msg = (
        f"Тема/контекст: {body.topic}\n"
        f"Язык: {body.language}\n"
        f"Тон: {body.tone}\n"
        f"Платформа: {body.platform}\n"
        "Верни только одну строку по формату."
    )

    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "AutoReels-Caption",
    }
    payload = {
        "model": OPENROUTER_MODEL_CAPTION,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.6 if body.mode == "short" else 0.7,
        "max_tokens": 1100 if body.mode == "short" else 2200,
    }
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        if r.status_code != 200:
            raise HTTPException(500, f"OpenRouter: {r.text[:300]}")
        out = r.json()["choices"][0]["message"]["content"]

    title, desc = _split_caption_line(out)
    if body.soften:
        title = soften_profanity(title)
        desc = soften_profanity(desc)

    hashtags = _hashtags_from_desc(desc, limit=10)
    return {"title": title, "description": desc, "hashtags": hashtags}

# =========== AI carousel per-slide prompts ===========
class CarouselPromptReq(BaseModel):
    topic: str
    style: str = "modern minimal"
    language: str = "ru"
    n: int = 6  # количество слайдов

@app.post("/ai/carousel/prompts")
async def ai_carousel_prompts(body: CarouselPromptReq):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise HTTPException(500, "OPENROUTER_API_KEY missing")

    sys_msg = (
        "Ты генератор промптов для изображений карусели Instagram. "
        "Верни ровно N строк, каждая — отдельный промпт для изображения, "
        "меняя ракурс/композицию/эмоцию/детали, но удерживая общую тему и стиль. "
        "Коротко, 1–2 предложения на строку. Без нумерации и лишнего текста."
    )
    user_msg = (
        f"Тема: {body.topic}\nСтиль: {body.style}\nЯзык: {body.language}\n"
        f"N: {body.n}\n"
        "Примеси: разные планы (крупный/средний/общий), игра света, текстуры, движение."
    )

    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "AutoReels-CarouselPrompts",
    }
    payload = {
        "model": OPENROUTER_MODEL_CAPTION,
        "messages": [
            {"role":"system", "content": sys_msg},
            {"role":"user", "content": user_msg}
        ],
        "temperature": 0.8,
        "max_tokens": 800
    }
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        if r.status_code != 200:
            raise HTTPException(500, f"OpenRouter: {r.text[:300]}")
        text = r.json()["choices"][0]["message"]["content"]

    lines = [ln.strip("-• \t") for ln in text.strip().split("\n") if ln.strip()]
    if len(lines) > body.n:
        lines = lines[:body.n]
    while len(lines) < body.n and lines:
        lines.append(lines[-1])

    return {"prompts": lines}

# ================= dev run ========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
