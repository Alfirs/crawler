import imaplib
import json
from typing import Dict, List

from app.config import settings
from app.services.google_drive import LOCAL_STORAGE_ROOT

LOG_PATH = LOCAL_STORAGE_ROOT / "_imap.log"


def _log(entry: Dict) -> None:
    entry["status"] = entry.get("status") or "logged"
    existing: List[Dict] = []
    if LOG_PATH.exists():
        try:
            existing = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    existing.append(entry)
    LOG_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def poll_inbox(limit: int = 10) -> Dict:
    """
    Placeholder IMAP poller: logs attempts. If IMAP creds are set, connects and lists recent UIDs.
    """
    if not settings.imap_host or not settings.imap_user or not settings.imap_password:
        _log({"status": "not_configured"})
        return {"status": "not_configured"}

    try:
        client = imaplib.IMAP4_SSL(settings.imap_host)
        client.login(settings.imap_user, settings.imap_password)
        client.select("INBOX")
        typ, data = client.search(None, "UNSEEN")
        uids = (data[0] or b"").split()
        recent = [uid.decode() for uid in uids[-limit:]]
        client.logout()
        _log({"status": "ok", "recent_unseen": recent})
        return {"status": "ok", "recent_unseen": recent}
    except Exception as exc:  # pragma: no cover - defensive
        _log({"status": "error", "error": str(exc)})
        return {"status": "error", "error": str(exc)}
