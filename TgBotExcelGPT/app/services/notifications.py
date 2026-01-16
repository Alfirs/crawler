import datetime as dt
import json
from typing import Dict, List

from app.services import email_client
from app.services.google_drive import LOCAL_STORAGE_ROOT

LOG_PATH = LOCAL_STORAGE_ROOT / "_notifications.log"


def _append_log(entry: Dict) -> None:
    entry["timestamp"] = dt.datetime.utcnow().isoformat() + "Z"
    existing: List[Dict] = []
    if LOG_PATH.exists():
        try:
            existing = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    existing.append(entry)
    LOG_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


async def send_summary(project_id: str, artifact: Dict, emails: List[str], telegram_ids: List[str]) -> Dict:
    attachments = []
    if artifact.get("excel"):
        attachments.append(artifact["excel"])
    email_status = None
    if emails:
        email_status = email_client.send_email(
            subject=f"[Project {project_id}] Итоговый отчёт",
            body="Сформирован итоговый отчёт по проекту. См. вложение/ссылки.",
            to=emails,
            attachments=[a for a in attachments if a],
        )
    entry = {
        "project_id": project_id,
        "artifact": artifact,
        "emails": emails,
        "telegram_ids": telegram_ids,
        "status": "queued",
        "email_status": email_status,
    }
    _append_log(entry)
    return entry
