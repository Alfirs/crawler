import json
from pathlib import Path
from typing import Dict, List, Optional

from app.services import google_drive


def _project_root(project_id: str) -> Path:
    return google_drive.LOCAL_STORAGE_ROOT / project_id


def _project_workspace(project_id: str) -> Path:
    base = _project_root(project_id) / "workspace"
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_items(project_id: str, data_type: str, items: List[Dict]) -> None:
    path = _project_workspace(project_id) / f"{data_type}_items.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def load_items(project_id: str, data_type: str) -> List[Dict]:
    path = _project_workspace(project_id) / f"{data_type}_items.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def has_items(project_id: str, data_type: str) -> bool:
    path = _project_workspace(project_id) / f"{data_type}_items.json"
    return path.exists()


def append_supplier_response(project_id: str, response: Dict) -> None:
    path = _project_workspace(project_id) / "supplier_responses.json"
    existing: List[Dict] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    existing.append(response)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def load_supplier_responses(project_id: str) -> List[Dict]:
    path = _project_workspace(project_id) / "supplier_responses.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_metadata(project_id: str, payload: Dict) -> None:
    path = _project_workspace(project_id) / "metadata.json"
    existing: Dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing.update(payload)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def load_metadata(project_id: str) -> Dict:
    path = _project_workspace(project_id) / "metadata.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def exists(project_id: str) -> bool:
    return _project_root(project_id).exists()


def list_reports(project_id: str) -> List[str]:
    reports_dir = google_drive.LOCAL_STORAGE_ROOT / project_id / "reports"
    if not reports_dir.exists():
        return []
    return [str(p) for p in reports_dir.glob("*") if p.is_file()]


def summary(project_id: str) -> Dict:
    return {
        "project_id": project_id,
        "has_spec": has_items(project_id, "spec"),
        "has_drawing": has_items(project_id, "drawing"),
        "has_procurement": has_items(project_id, "procurement"),
        "supplier_responses": len(load_supplier_responses(project_id)),
        "reports": list_reports(project_id),
        "metadata": load_metadata(project_id),
    }


def list_projects() -> List[str]:
    root = google_drive.LOCAL_STORAGE_ROOT
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir()])
