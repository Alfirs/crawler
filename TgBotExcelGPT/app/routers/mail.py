from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.services import email_client, imap_poll

router = APIRouter(prefix="/mail", tags=["mail"])


class SendEmailPayload(BaseModel):
    subject: str
    body: str
    to: List[EmailStr]
    attachments: Optional[List[str]] = None


@router.post("/send")
async def send_mail(payload: SendEmailPayload) -> dict:
    result = email_client.send_email(
        subject=payload.subject,
        body=payload.body,
        to=[str(addr) for addr in payload.to],
        attachments=payload.attachments,
    )
    return {"status": result}


@router.get("/poll")
async def poll_inbox(limit: int = 10) -> dict:
    result = imap_poll.poll_inbox(limit=limit)
    return result
