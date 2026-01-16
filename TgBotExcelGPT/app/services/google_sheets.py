import asyncio
import json
from pathlib import Path
from typing import Any, List

from app.services.google_drive import LOCAL_STORAGE_ROOT

SHEETS_STORAGE = LOCAL_STORAGE_ROOT / "_sheets"
SHEETS_STORAGE.mkdir(parents=True, exist_ok=True)


def _sheet_path(sheet_id: str) -> Path:
    return SHEETS_STORAGE / f"{sheet_id or 'default'}.json"


async def fetch_rows(sheet_id: str, range_name: str) -> List[List[Any]]:
    """
    Placeholder for Google Sheets read.
    """
    await asyncio.sleep(0)
    path = _sheet_path(sheet_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


async def append_rows(sheet_id: str, rows: List[List[Any]]) -> str:
    """
    Placeholder for Google Sheets append. Writes to local JSON.
    """
    await asyncio.sleep(0)
    path = _sheet_path(sheet_id)
    existing: List[List[Any]] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    existing.extend(rows)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"{sheet_id}!A1"
