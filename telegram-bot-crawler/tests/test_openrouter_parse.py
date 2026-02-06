"""Tests for OpenRouter JSON parsing."""

from __future__ import annotations

from tbcrawl.director.openrouter_director import _extract_json_object


def test_extract_json_object_with_fences() -> None:
    text = "```json\n{\"action_type\":\"send_text\",\"value\":\"10\"}\n```"
    parsed = _extract_json_object(text)
    assert parsed["action_type"] == "send_text"
    assert parsed["value"] == "10"


def test_extract_json_object_with_extra_text() -> None:
    text = "Result:\n{\"action_type\":\"click_inline\",\"row\":0,\"col\":1}\nThanks"
    parsed = _extract_json_object(text)
    assert parsed["action_type"] == "click_inline"
    assert parsed["row"] == 0
