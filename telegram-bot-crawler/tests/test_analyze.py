"""Tests for analyze spec generation."""

from __future__ import annotations

import json
from pathlib import Path

from tbcrawl.analyze import analyze_artifacts


def test_analyze_creates_spec(tmp_path: Path) -> None:
    bot_map = {
        "metadata": {"bot_username": "test_bot"},
        "nodes": {
            "root": {
                "id": "root",
                "text": "Welcome",
                "buttons": [[{"text": "Start", "row": 0, "col": 0, "data": "x"}]],
                "screen_type": "menu",
            }
        },
        "edges": [
            {
                "from": "root",
                "to": "root",
                "action": {"type": "click", "value": "Start", "row": 0, "col": 0},
            }
        ],
    }
    input_dir = tmp_path / "output"
    input_dir.mkdir()
    (input_dir / "bot_map.json").write_text(json.dumps(bot_map), encoding="utf-8")
    (input_dir / "golden.jsonl").write_text("{}", encoding="utf-8")

    output_path = input_dir / "spec.md"
    analyze_artifacts(input_dir, output_path)
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Specification" in content
