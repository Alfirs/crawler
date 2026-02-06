from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
import json


class ScreenType(str, Enum):
    MENU = "menu"
    INPUT_REQUIRED = "input_required"
    TERMINAL = "terminal"


class ActionType(str, Enum):
    CLICK = "click"
    SEND_TEXT = "send_text"


@dataclass(frozen=True)
class Button:
    text: str
    url: str | None = None

    def is_url(self) -> bool:
        return self.url is not None


@dataclass(frozen=True)
class Action:
    type: ActionType
    value: str


@dataclass(frozen=True)
class MediaInfo:
    has_media: bool = False
    types: list[str] = field(default_factory=list)


@dataclass
class Node:
    id: str
    text: str
    buttons: list[list[Button]]
    screen_type: ScreenType
    example_path: list[Action]
    media: MediaInfo
    created_at: datetime


@dataclass
class Edge:
    from_node: str
    to_node: str
    action: Action
    created_at: datetime


@dataclass
class BotMap:
    metadata: dict[str, Any]
    nodes: dict[str, Node]
    edges: list[Edge]


@dataclass(frozen=True)
class RawLogEntry:
    timestamp: datetime
    event_type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class FlowArtifacts:
    bot_map: BotMap
    raw_log: list[RawLogEntry]


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.utcnow()


def load_bot_map(path: Path) -> BotMap:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)

    nodes: dict[str, Node] = {}
    for node_id, node_data in data.get("nodes", {}).items():
        buttons: list[list[Button]] = []
        for row in node_data.get("buttons", []) or []:
            buttons.append(
                [Button(text=btn.get("text", ""), url=btn.get("url")) for btn in row]
            )

        example_path = []
        for action in node_data.get("example_path", []) or []:
            example_path.append(
                Action(type=ActionType(action["type"]), value=action["value"])
            )

        media_data = node_data.get("media", {}) or {}
        media = MediaInfo(
            has_media=bool(media_data.get("has_media", False)),
            types=list(media_data.get("types", []) or []),
        )

        nodes[node_id] = Node(
            id=node_id,
            text=node_data.get("text", ""),
            buttons=buttons,
            screen_type=ScreenType(node_data.get("screen_type", "terminal")),
            example_path=example_path,
            media=media,
            created_at=_parse_datetime(node_data.get("created_at")),
        )

    edges: list[Edge] = []
    for edge_data in data.get("edges", []) or []:
        action_data = edge_data.get("action", {})
        action = Action(
            type=ActionType(action_data.get("type", "send_text")),
            value=action_data.get("value", ""),
        )
        edges.append(
            Edge(
                from_node=edge_data.get("from", ""),
                to_node=edge_data.get("to", ""),
                action=action,
                created_at=_parse_datetime(edge_data.get("created_at")),
            )
        )

    metadata = dict(data.get("metadata", {}) or {})

    return BotMap(metadata=metadata, nodes=nodes, edges=edges)


def load_raw_log(path: Path) -> list[RawLogEntry]:
    entries: list[RawLogEntry] = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        entries.append(
            RawLogEntry(
                timestamp=_parse_datetime(data.get("timestamp")),
                event_type=str(data.get("event_type", "")),
                data=dict(data.get("data", {}) or {}),
            )
        )
    return entries


def load_artifacts(input_dir: Path) -> FlowArtifacts:
    bot_map_path = input_dir / "bot_map.json"
    raw_log_path = input_dir / "raw_log.jsonl"
    if not bot_map_path.exists():
        raise FileNotFoundError(f"Missing bot_map.json at {bot_map_path}")
    bot_map = load_bot_map(bot_map_path)
    raw_log = load_raw_log(raw_log_path)
    return FlowArtifacts(bot_map=bot_map, raw_log=raw_log)
