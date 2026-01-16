import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional

from app.config import settings
from app.services.google_drive import LOCAL_STORAGE_ROOT

LOG_PATH = LOCAL_STORAGE_ROOT / "_email.log"


def _log(entry: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def send_email(subject: str, body: str, to: List[str], attachments: Optional[List[Path]] = None) -> dict:
    """
    Sends email via SMTP if configured; otherwise logs to file and returns pseudo status.
    """
    attachments = attachments or []
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        _log(f"SMTP not configured. Subject: {subject}. To: {to}. Attachments: {[str(a) for a in attachments]}")
        return {"status": "logged", "message": "SMTP not configured"}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = ", ".join(to)
    msg.set_content(body)

    for attachment in attachments:
        path = Path(attachment)
        if not path.exists():
            continue
        data = path.read_bytes()
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=path.name)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    return {"status": "sent", "to": to}
