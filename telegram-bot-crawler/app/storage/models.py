from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SessionState:
    user_id: int
    current_node_id: str
    data: dict[str, Any] = field(default_factory=dict)
    pending_input_type: str | None = None
    last_prompt: str | None = None
    last_buttons: dict[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


@dataclass(frozen=True)
class InteractionLog:
    user_id: int
    node_id: str
    user_message: str
    bot_message: str
    chosen_action: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
