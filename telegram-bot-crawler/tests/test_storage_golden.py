"""Tests for golden dataset logging."""

from __future__ import annotations

from pathlib import Path

from tbcrawl.storage import Storage


def test_golden_log_written(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    storage.log_golden_step({"step": 1, "state_in": {}, "user_action": {}})
    golden_path = tmp_path / "golden.jsonl"
    assert golden_path.exists()
    content = golden_path.read_text(encoding="utf-8").strip()
    assert content


def test_backend_memory_written(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    storage.log_backend_memory({"step": 1, "analysis": {"screen_label": "X"}})
    backend_path = tmp_path / "backend_memory.jsonl"
    assert backend_path.exists()
    content = backend_path.read_text(encoding="utf-8").strip()
    assert content
