import asyncio
import os
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from app.config import settings

LOCAL_STORAGE_ROOT = Path(os.getenv("LOCAL_STORAGE_ROOT", "data"))


async def save_upload(project_id: str, uploaded: UploadFile) -> str:
    """
    Saves the uploaded file locally (stand-in for Google Drive upload).
    Returns a pseudo-link that can later be replaced with the real Drive URL.
    """
    LOCAL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    target_dir = LOCAL_STORAGE_ROOT / project_id
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / uploaded.filename
    content = await uploaded.read()
    target_path.write_bytes(content)

    # Placeholder for future Drive upload; return local path as link for now.
    return str(target_path)


async def upload_to_drive(file_path: Path, folder_id: Optional[str] = None) -> str:
    """
    Placeholder for real Google Drive upload. Returns the path for now.
    """
    await asyncio.sleep(0)  # keep signature async-compatible
    folder = folder_id or settings.google_drive_folder_id
    return f"drive://{folder or 'local'}/{file_path.name}"
