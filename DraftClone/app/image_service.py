import os
import time
import logging
from pathlib import Path
from typing import List, Optional

import httpx

logger = logging.getLogger("image_service")

API_BASE = os.getenv("FOURO_API_BASE", "https://api.kie.ai/api/v1/gpt4o-image")
API_KEY = os.getenv("FOURO_API_KEY", "")
FOURO_SIZE = os.getenv("FOURO_SIZE", "1:1")
FOURO_VARIANTS = int(os.getenv("FOURO_VARIANTS", "1"))
FOURO_ENHANCE = os.getenv("FOURO_IS_ENHANCE", "false").lower() in {"1", "true", "yes", "on"}
FOURO_UPLOAD_CN = os.getenv("FOURO_UPLOAD_CN", "false").lower() in {"1", "true", "yes", "on"}
FOURO_ENABLE_FALLBACK = os.getenv("FOURO_ENABLE_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}
FOURO_FALLBACK_MODEL = os.getenv("FOURO_FALLBACK_MODEL", "FLUX_MAX")
POLL_INTERVAL = float(os.getenv("FOURO_POLL_INTERVAL", "5"))
POLL_TIMEOUT = float(os.getenv("FOURO_POLL_TIMEOUT", "120"))
PROMPT_TEMPLATE = os.getenv(
    "FOURO_PROMPT_TEMPLATE",
    "Design a clean Instagram slide with theme '{theme_name}'. Title: {title}. Details: {details}.",
)

if not API_KEY:
    logger.warning("FOURO_API_KEY is not set; image generation will fail.")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def _create_task(payload: dict) -> str:
    url = f"{API_BASE}/generate"
    resp = httpx.post(url, headers=_headers(), json=payload, timeout=30)
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"4o image generation failed: {data}")
    task_id = data.get("data", {}).get("taskId")
    if not task_id:
        raise RuntimeError(f"4o response missing taskId: {data}")
    return task_id


def _poll_task(task_id: str) -> List[str]:
    url = f"{API_BASE}/record-info"
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        resp = httpx.get(url, headers=_headers(), params={"taskId": task_id}, timeout=30)
        payload = resp.json()
        if payload.get("code") != 200:
            logger.warning("4o poll failed for %s: %s", task_id, payload)
            time.sleep(POLL_INTERVAL)
            continue
        data = payload.get("data") or {}
        status = data.get("status")
        if status == "GENERATING":
            time.sleep(POLL_INTERVAL)
            continue
        if status == "SUCCESS":
            info = data.get("info") or {}
            response_block = data.get("response") or {}
            result_urls = (
                info.get("result_urls")
                or info.get("resultUrls")
                or response_block.get("result_urls")
                or response_block.get("resultUrls")
                or data.get("result_urls")
                or data.get("resultUrls")
            )
            if not result_urls:
                logger.error("4o task %s success but payload missing URLs: %s", task_id, payload)
                raise RuntimeError(f"4o task {task_id} succeeded but no result urls")
            return result_urls
        else:
            raise RuntimeError(f"4o task {task_id} failed: {status} - {payload.get('msg')}")
    raise TimeoutError(f"Timed out waiting for 4o task {task_id}")


def _download(url: str, dst: Path) -> None:
    with httpx.stream("GET", url, timeout=120) as resp:
        resp.raise_for_status()
        with dst.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)


def build_prompt(slide: dict, theme_meta: dict) -> str:
    title = slide.get("title") or ""
    details_parts = []
    if slide.get("subtitle"):
        details_parts.append(slide["subtitle"])
    details_parts.extend(slide.get("bullets") or [])
    details = " | ".join(details_parts)
    return PROMPT_TEMPLATE.format(
        theme_name=theme_meta.get("name", "Midnight"),
        title=title,
        details=details,
    )


def generate_slide_image(slide: dict, theme_meta: dict, out_path: Path) -> None:
    prompt = build_prompt(slide, theme_meta)
    payload = {
        "prompt": prompt,
        "size": FOURO_SIZE,
        "nVariants": FOURO_VARIANTS,
        "isEnhance": FOURO_ENHANCE,
        "uploadCn": FOURO_UPLOAD_CN,
        "enableFallback": FOURO_ENABLE_FALLBACK,
        "fallbackModel": FOURO_FALLBACK_MODEL,
    }
    task_id = _create_task(payload)
    urls = _poll_task(task_id)
    _download(urls[0], out_path)
