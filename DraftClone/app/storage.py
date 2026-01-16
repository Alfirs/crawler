from pathlib import Path
import os
import zipfile
from typing import List, Tuple
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parent
ASSETS_ROOT = BASE_DIR / "storage"
OUT_DIR = ASSETS_ROOT / "posts"
BACKGROUND_DIR = ASSETS_ROOT / "backgrounds"


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)


def _safe_ext(filename: str) -> str:
    allowed = {".png", ".jpg", ".jpeg", ".webp"}
    suffix = Path(filename or "").suffix.lower()
    if suffix not in allowed:
        return ".png"
    return suffix


def _as_absolute(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate.resolve()


def _as_web_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(ASSETS_ROOT)
        return f"/assets/{rel.as_posix()}"
    except ValueError:
        rel = path.resolve().relative_to(BASE_DIR)
        return "/" + rel.as_posix().lstrip("/")


def save_images_zip(image_paths: List[str], post_id: int) -> Tuple[str, str, List[str]]:
    resolved_paths = [_as_absolute(p) for p in image_paths]
    post_dir = OUT_DIR / str(post_id)
    post_dir.mkdir(parents=True, exist_ok=True)

    final_paths = []
    for idx, src in enumerate(resolved_paths, start=1):
        if not src.exists():
            raise FileNotFoundError(f"Image not found: {src}")
        dst = post_dir / f"slide_{idx:02d}.png"
        os.replace(src, dst)
        final_paths.append(dst)

    zip_path = post_dir / "carousel.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in final_paths:
            archive.write(path, arcname=path.name)

    zip_web_path = _as_web_path(zip_path)
    image_web_paths = [_as_web_path(p) for p in final_paths]
    return str(zip_path), zip_web_path, image_web_paths


def save_background_image(post_id: int, filename: str, data: bytes) -> str:
    if not data:
        raise ValueError("Empty file")
    target_dir = BACKGROUND_DIR / str(post_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = _safe_ext(filename)
    name = f"{uuid4().hex}{ext}"
    path = target_dir / name
    path.write_bytes(data)
    return _as_web_path(path)
