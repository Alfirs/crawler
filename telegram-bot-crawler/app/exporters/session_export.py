from __future__ import annotations

import json

from app.storage.models import InteractionLog


def export_logs(logs: list[InteractionLog]) -> str:
    payload = [
        {
            "user_id": log.user_id,
            "timestamp": log.timestamp.isoformat(),
            "node_id": log.node_id,
            "user_message": log.user_message,
            "bot_message": log.bot_message,
            "chosen_action": log.chosen_action,
        }
        for log in logs
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)
