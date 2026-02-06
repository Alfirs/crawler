from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from app.storage.db import Database
from app.storage.models import InteractionLog, SessionState


class SessionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def get_or_create_session(self, user_id: int, root_node_id: str) -> SessionState:
        existing = await asyncio.to_thread(self._get_session, user_id)
        if existing:
            return existing
        session = SessionState(user_id=user_id, current_node_id=root_node_id)
        await self.save_session(session)
        return session

    async def save_session(self, session: SessionState) -> None:
        session.touch()
        await asyncio.to_thread(self._save_session, session)

    async def log_interaction(self, log: InteractionLog) -> None:
        await asyncio.to_thread(self._log_interaction, log)

    async def export_logs(self, user_id: int | None = None) -> list[InteractionLog]:
        return await asyncio.to_thread(self._export_logs, user_id)

    def _get_session(self, user_id: int) -> SessionState | None:
        placeholder = self.db.placeholder
        row = self.db.fetchone(
            f"SELECT user_id, current_node_id, data, pending_input_type, last_prompt, last_buttons, updated_at "
            f"FROM sessions WHERE user_id = {placeholder}",
            (user_id,),
        )
        if not row:
            return None
        return self._row_to_session(row)

    def _save_session(self, session: SessionState) -> None:
        placeholder = self.db.placeholder
        data_json = json.dumps(session.data, ensure_ascii=False)
        buttons_json = json.dumps(session.last_buttons, ensure_ascii=False)
        sql = (
            "INSERT INTO sessions (user_id, current_node_id, data, pending_input_type, last_prompt, last_buttons, updated_at) "
            f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "current_node_id=excluded.current_node_id, "
            "data=excluded.data, "
            "pending_input_type=excluded.pending_input_type, "
            "last_prompt=excluded.last_prompt, "
            "last_buttons=excluded.last_buttons, "
            "updated_at=excluded.updated_at"
        )
        self.db.execute(
            sql,
            (
                session.user_id,
                session.current_node_id,
                data_json,
                session.pending_input_type,
                session.last_prompt,
                buttons_json,
                session.updated_at.isoformat(),
            ),
        )

    def _log_interaction(self, log: InteractionLog) -> None:
        placeholder = self.db.placeholder
        sql = (
            "INSERT INTO logs (user_id, timestamp, node_id, user_message, bot_message, chosen_action) "
            f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})"
        )
        self.db.execute(
            sql,
            (
                log.user_id,
                log.timestamp.isoformat(),
                log.node_id,
                log.user_message,
                log.bot_message,
                log.chosen_action,
            ),
        )

    def _export_logs(self, user_id: int | None) -> list[InteractionLog]:
        placeholder = self.db.placeholder
        if user_id is None:
            rows = self.db.fetchall(
                "SELECT user_id, timestamp, node_id, user_message, bot_message, chosen_action FROM logs ORDER BY timestamp",
                (),
            )
        else:
            rows = self.db.fetchall(
                f"SELECT user_id, timestamp, node_id, user_message, bot_message, chosen_action "
                f"FROM logs WHERE user_id = {placeholder} ORDER BY timestamp",
                (user_id,),
            )
        return [self._row_to_log(row) for row in rows]

    def _row_to_session(self, row: Any) -> SessionState:
        data = json.loads(row["data"]) if row["data"] else {}
        buttons = json.loads(row["last_buttons"]) if row["last_buttons"] else {}
        updated_at = datetime.fromisoformat(row["updated_at"])
        return SessionState(
            user_id=int(row["user_id"]),
            current_node_id=str(row["current_node_id"]),
            data=data,
            pending_input_type=row["pending_input_type"],
            last_prompt=row["last_prompt"],
            last_buttons=buttons,
            updated_at=updated_at,
        )

    def _row_to_log(self, row: Any) -> InteractionLog:
        timestamp = datetime.fromisoformat(row["timestamp"])
        return InteractionLog(
            user_id=int(row["user_id"]),
            node_id=str(row["node_id"]),
            user_message=str(row["user_message"] or ""),
            bot_message=str(row["bot_message"] or ""),
            chosen_action=str(row["chosen_action"] or ""),
            timestamp=timestamp,
        )
