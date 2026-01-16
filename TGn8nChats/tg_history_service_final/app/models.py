from typing import Literal

from pydantic import BaseModel, StrictInt


class DialogItem(BaseModel):
    chatId: StrictInt
    title: str
    lastTs: StrictInt


class ChatHistoryRequest(BaseModel):
    chatId: StrictInt
    count: StrictInt = 50


class MessageItem(BaseModel):
    chatId: StrictInt
    timestamp: StrictInt
    fromMe: bool
    typeMessage: Literal["textMessage"] = "textMessage"
    textMessage: str
