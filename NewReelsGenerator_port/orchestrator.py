import uuid
import json
import sqlite3
import threading
import time
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

import random

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# === РџРѕРґРєР»СЋС‡Р°РµРј С‚РІРѕРё РјРѕРґСѓР»Рё ===
import ReelsGen as RG
import GUIreels as GP
from GUIreels import do_post
from prompts_loader import (
    load_prompt_for_account,
    load_footer_for_account,
    load_title_description_separator,
)
import re as _re


DB_PATH = Path("jobs.db")


# ========== Р‘Р” ==========
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs(
      id TEXT PRIMARY KEY,
      kind TEXT,
      status TEXT,
      payload TEXT,
      result TEXT,
      created_at TEXT,
      started_at TEXT,
      finished_at TEXT
    )
    """)
    con.commit()
    con.close()

def clean_text(text: str) -> str:
    """РЈР±РёСЂР°РµС‚ СЃС‚СЂРѕРєРё, РіРґРµ С‚РѕР»СЊРєРѕ РїСЂРѕР±РµР»С‹/РЅРµРІРёРґРёРјС‹Рµ СЃРёРјРІРѕР»С‹,
    Рё РЅРµ РґРѕРїСѓСЃРєР°РµС‚ РїРѕРґСЂСЏРґ Р±РѕР»РµРµ РѕРґРЅРѕР№ РїСѓСЃС‚РѕР№ СЃС‚СЂРѕРєРё."""
    clean_lines = []
    for line in text.splitlines():
        if line.strip():  # СЃС‚СЂРѕРєР° СЃРѕРґРµСЂР¶РёС‚ С‚РµРєСЃС‚
            clean_lines.append(line.rstrip())
        else:
            # РґРѕР±Р°РІР»СЏРµРј РїСѓСЃС‚СѓСЋ СЃС‚СЂРѕРєСѓ С‚РѕР»СЊРєРѕ РµСЃР»Рё РїРѕСЃР»РµРґРЅСЏСЏ СЃС‚СЂРѕРєР° РЅРµ РїСѓСЃС‚Р°СЏ
            if clean_lines and clean_lines[-1] != "":
                clean_lines.append("")
    return "\n".join(clean_lines).strip()

def sanitize_cta(text: str) -> str:
    """Legacy CTA sanitizer now disabled by default."""
    return text

def strip_numeric_list_prefix(text: str) -> str:
    if not text:
        return ""
    return text.strip()

def remove_forbidden_phrases(text: str) -> str:
    if not text:
        return ""
    forbidden_exact = [
        "Было полезно? Жми лайк",
        "Было полезно - жми лайк",
        "Было полезно? жми лайк",
    ]
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(phrase.lower() in lowered for phrase in forbidden_exact):
            continue
        if "было полезно" in lowered and ("лайк" in lowered or "подпис" in lowered):
            continue
        cleaned_lines.append(line.rstrip())
    cleaned = "\n".join(cleaned_lines).strip()
    if not cleaned:
        return ""
    for idx, ch in enumerate(cleaned):
        if ch.isalpha():
            cleaned = cleaned[:idx] + ch.upper() + cleaned[idx + 1:]
            break
    return cleaned

def normalize_title_lines(title: str) -> str:
    """Ensure each title line has at least two words while preserving original casing."""
    if not title:
        return ""
    lines = [ln.strip() for ln in title.splitlines()]
    result: list[str] = []
    carry: str | None = None
    for line in lines:
        if not line:
            continue
        words = line.split()
        if len(words) < 2:
            if carry is None:
                carry = line
            else:
                carry = f"{carry} {line}".strip()
            continue
        if carry is not None:
            line = f"{carry} {line}".strip()
            carry = None
        elif result and len(result[-1].split()) < 2:
            line = f"{result.pop()} {line}".strip()
        result.append(line)
    if carry is not None:
        if result:
            result[-1] = f"{result[-1]} {carry}".strip()
        else:
            result.append(carry)
    pieces = []
    prev_tail = ''
    for idx, line in enumerate(result):
        if not line:
            continue
        segment = line.strip()
        if idx > 0 and segment:
            first_char = segment[0]
            tail = prev_tail.rstrip() if prev_tail else ''
            if first_char.isalpha() and tail and tail[-1] not in ' .!?;:,"\'()[]{}<>-':
                segment = first_char.lower() + segment[1:]
        pieces.append(segment)
        prev_tail = segment
    combined = ' '.join(pieces).strip()
    combined = ' '.join(combined.split())
    return combined

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


init_db()


# ========== API ==========
app = FastAPI(title="Reels Orchestrator", version="0.1.0")


class JobRequest(BaseModel):
    kind: str                 # "generate" РёР»Рё "post"
    payload: Dict[str, Any]   # РєРѕРЅС„РёРі Р·Р°РґР°С‡Рё


@app.post("/jobs")
def create_job(req: JobRequest):
    try:
        if req.kind not in ("generate", "post"):
            raise HTTPException(400, "kind must be 'generate' or 'post'")
        job_id = str(uuid.uuid4())
        with db() as con:
            con.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)", (
                job_id, req.kind, "queued",
                json.dumps(req.payload, ensure_ascii=False),
                None, datetime.utcnow().isoformat(), None, None
            ))
        return {"id": job_id, "status": "queued"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise


@app.get("/jobs")
def list_jobs(limit: int = 50):
    with db() as con:
        cur = con.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    with db() as con:
        r = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Not found")
        return dict(r)
        
        
@app.get("/ping")
def ping():
    return {"msg": "pong"}


# ========== Р’РѕСЂРєРµСЂС‹ ==========
STOP = False


def run_worker():
    while not STOP:
        try:
            with db() as con:
                r = con.execute(
                    "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1"
                ).fetchone()
            if not r:
                time.sleep(1)
                continue

            job = dict(r)
            job_id = job["id"]
            payload = json.loads(job["payload"])
            kind = job["kind"]

            # РїРѕРјРµС‡Р°РµРј РєР°Рє running
            with db() as con:
                con.execute(
                    "UPDATE jobs SET status='running', started_at=? WHERE id=?",
                    (datetime.utcnow().isoformat(), job_id)
                )

            # РІС‹РїРѕР»РЅСЏРµРј Р·Р°РґР°С‡Сѓ
            if kind == "generate":
                result = do_generate(payload)
            elif kind == "post":
                result = do_post(payload)
            else:
                result = {"error": f"Unknown kind {kind}"}

            # done
            with db() as con:
                con.execute(
                    "UPDATE jobs SET status='done', finished_at=?, result=? WHERE id=?",
                    (datetime.utcnow().isoformat(), json.dumps(result, ensure_ascii=False), job_id)
                )
        except Exception as e:
            traceback.print_exc()
            if "job_id" in locals():
                with db() as con:
                    con.execute(
                        "UPDATE jobs SET status='failed', finished_at=?, result=? WHERE id=?",
                        (datetime.utcnow().isoformat(), json.dumps({"error": str(e)}), job_id)
                    )


threading.Thread(target=run_worker, daemon=True).start()

# ========== Р РµР°Р»РёР·Р°С†РёСЏ post ==========
def do_generate(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Р’С‹Р·С‹РІР°РµС‚ РіРµРЅРµСЂР°С‚РѕСЂ СЂРѕР»РёРєРѕРІ (ReelsGen) СЃ С‡Р°РЅРєРѕРІРѕР№ РіРµРЅРµСЂР°С†РёРµР№ Рё С„РёР»СЊС‚СЂР°С†РёРµР№ РїСѓСЃС‚С‹С… РѕРїРёСЃР°РЅРёР№."""
    out_dir = Path(cfg["out"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # РјР°СЃРєРё
    templates = RG.load_templates()
    mask = cfg.get("mask")
    caption_mask = cfg.get("caption_mask")
    if cfg.get("template") and cfg["template"] in templates:
        tpl = templates[cfg["template"]]
        mask = tpl.get("mask") or tpl.get("title")
        caption_mask = tpl.get("caption_mask") or tpl.get("caption")

    # РёСЃС‚РѕС‡РЅРёРєРё
    mode = cfg.get("mode", "titles")
    count = int(cfg.get("count", 1))
    titles, descriptions = [], []
    # Load required account-specific prompt
    account = cfg.get("account")
    if not account:
        raise ValueError("'account' is required in payload to select account-specific prompt.")
    prompt_text = load_prompt_for_account(account, mode)
    footer_text = load_footer_for_account(account)
    separator = load_title_description_separator(account)

    if mode == "titles":
        titles = Path(cfg["titles"]).read_text(encoding="utf-8").splitlines()
        titles = [t.strip() for t in titles if t.strip()]
        random.shuffle(titles)
        titles = titles[:count]

        # С‡Р°РЅРєРѕРІР°СЏ РіРµРЅРµСЂР°С†РёСЏ РѕРїРёСЃР°РЅРёР№ (РїРѕ 5, РєР°Рє РІ ReelsGen)
        descriptions = []
        # Use batch of 5 (restored), relying on stricter JSON mapping in ReelsGen
        chunk_size = 5
        for i in range(0, len(titles), chunk_size):
            chunk = titles[i:i+chunk_size]
            # Simplified robust JSON path with strong fallbacks
            descs = RG.generate_descriptions_batch_json(chunk, system_prompt=prompt_text)
            descriptions.extend(descs)

    else:
        topics = Path(cfg["topics"]).read_text(encoding="utf-8").splitlines()
        topics = [t.strip() for t in topics if t.strip()]
        random.shuffle(topics)
        topics = topics[:count]

        titles, descriptions = [], []
        chunk_size = 5
        for i in range(0, len(topics), chunk_size):
            chunk = topics[i:i+chunk_size]
            try:
                pairs = RG.generate_titles_descriptions_batch_json_points(
                    chunk, system_prompt=prompt_text, separator=separator
                )
            except Exception:
                pairs = RG.generate_titles_descriptions_batch_json(
                    chunk, system_prompt=prompt_text, separator=separator
                )
            for t, d in pairs:
                titles.append(t)
                descriptions.append(d)

    # С„РёР»СЊС‚СЂСѓРµРј РїСѓСЃС‚С‹Рµ РѕРїРёСЃР°РЅРёСЏ
    # Debug dump of raw generated descriptions
    try:
        import csv as _csv
        with (out_dir / "debug_generation.csv").open("w", newline="", encoding="utf-8-sig") as fdbg:
            w = _csv.writer(fdbg)
            w.writerow(["title", "desc_len", "empty", "head"])
            for t, d in zip(titles, descriptions):
                txt = d or ""
                w.writerow([t, len(txt), int(len(txt) == 0), txt[:120].replace("\n", " ")])
    except Exception:
        pass

    # Temporarily disable skipping for diagnostics
    valid_pairs = list(zip(titles, descriptions))
    skipped = []

    VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
    video_dir = Path(cfg["video_dir"])
    videos = sorted(
        [p for p in video_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS],
        key=lambda p: p.name.lower()
    )
    if not videos:
        raise ValueError(f"Р’ {video_dir} РЅРµ РЅР°Р№РґРµРЅРѕ РІРёРґРµРѕ СЃ СЂР°СЃС€РёСЂРµРЅРёСЏРјРё {sorted(VIDEO_EXTS)}")     
    keep_original_audio = bool(cfg.get("keep_original_audio"))
    music_mode = cfg.get("music_mode", "random")
    music_dir_raw = cfg.get("music_dir")
    music_dir = Path(music_dir_raw).resolve() if music_dir_raw else None
    if not keep_original_audio:
        if not music_dir:
            raise ValueError("Provide 'music_dir' or set 'keep_original_audio: true' for account config.")
        if not music_dir.exists():
            raise ValueError(f"Music directory not found: {music_dir}")

    full_vertical_video = bool(cfg.get("full_vertical_video"))
    gradient_height_raw = cfg.get("top_gradient_height")
    gradient_strength_raw = cfg.get("top_gradient_strength")
    try:
        top_gradient_height = int(gradient_height_raw) if gradient_height_raw not in (None, "") else None
    except (TypeError, ValueError):
        top_gradient_height = None
    try:
        top_gradient_strength = float(gradient_strength_raw) if gradient_strength_raw not in (None, "") else None
    except (TypeError, ValueError):
        top_gradient_strength = None

    from itertools import cycle, islice

    pairs = valid_pairs[:count]   # РіР°СЂР°РЅС‚РёСЂРѕРІР°РЅРЅРѕ РіРµРЅРµСЂРёРј СЂРѕРІРЅРѕ 'count' СЂРѕР»РёРєРѕРІ (РµСЃР»Рё РѕРїРёСЃР°РЅРёР№ С…РІР°С‚РёС‚)
    results = []
    for idx, (src, (title, desc)) in enumerate(zip(islice(cycle(videos), len(pairs)), pairs), start=1):
        title = strip_numeric_list_prefix(clean_text(title))
        title = normalize_title_lines(title)
        desc = clean_text(desc)
        desc = remove_forbidden_phrases(desc)
        desc = sanitize_cta(desc)
        # Append account CTA/footer if provided and not already present
        if footer_text:
            try:
                if footer_text.strip() not in desc:
                    desc = desc.rstrip() + "\n\n" + footer_text.strip()
            except Exception:
                # Best-effort; ignore if anything goes wrong
                pass
        desc_len = len(desc)
        if desc_len > GP.MAX_DESCRIPTION:
            skipped.append(f"too_long:{desc_len}:{title}")
            continue
        if keep_original_audio:
            music = None
        else:
            music = RG.pick_music(str(music_dir), music_mode)
        reel_idx = len(results) + 1
        out_file = out_dir / f"reel_{reel_idx:03d}.mp4"

        overlay_mode = (cfg.get("caption_overlay") or "text").lower()
        if overlay_mode == "dots":
            RG.process_video_with_dots(
                video_path=str(src),
                music_path=music,
                out_path=str(out_file),
                title=title,
                description=desc,
                mask=tuple(mask),
                caption_mask=tuple(caption_mask),
                title_font=cfg["font"],
                title_size=int(cfg.get("title_size", 48)),
                text_color=cfg.get("text_color", "#FFFFFF"),
                box_color=cfg.get("box_color", "#000000"),
                box_alpha=float(cfg.get("box_alpha", 0.5)),
                dots_image=cfg.get("dots_image"),
                dots_scale=float(cfg.get("dots_scale", 0.6)),
                highlight_color=cfg.get("highlight_color"),
                full_vertical=full_vertical_video,
                top_gradient_height=top_gradient_height,
                top_gradient_strength=top_gradient_strength,
            )
        else:
            RG.process_video(
                video_path=str(src),
                music_path=music,
                out_path=str(out_file),
                title=title,
                description=desc,
                mask=tuple(mask),
                caption_mask=tuple(caption_mask),
                title_font=cfg["font"],
                caption_font=cfg["font"],
                title_size=int(cfg.get("title_size", 48)),
                caption_size=int(cfg.get("caption_size", 36)),
                text_color=cfg.get("text_color", "#FFFFFF"),
                box_color=cfg.get("box_color", "#000000"),
                box_alpha=float(cfg.get("box_alpha", 0.5)),
                full_vertical=full_vertical_video,
                top_gradient_height=top_gradient_height,
                top_gradient_strength=top_gradient_strength,
            )
        results.append({"path": str(out_file), "caption": desc, "title": title})

    # === СЃРѕС…СЂР°РЅСЏРµРј results.csv ===
    import csv
    csv_path = out_dir / "results.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "title", "description"])
        for res in results:
            writer.writerow([Path(res["path"]).name, clean_text(res["title"]),
                 clean_text(res["caption"])])

    # === СЃРѕС…СЂР°РЅСЏРµРј skipped.txt ===
    if skipped:
        with (out_dir / "skipped.txt").open("w", encoding="utf-8") as f:
            for t in skipped:
                f.write(t + "\n")

    return {
        "generated": len(results),
        "skipped": len(skipped),
        "assets": results,
    }
