from __future__ import annotations

from pathlib import Path

from app.flow.loader import load_artifacts


def test_load_bot_map() -> None:
    root = Path(__file__).resolve().parents[1]
    artifacts = load_artifacts(root / "input")
    assert artifacts.bot_map.nodes
    root_id = next(iter(artifacts.bot_map.nodes))
    node = artifacts.bot_map.nodes[root_id]
    assert node.text.startswith("\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435")
