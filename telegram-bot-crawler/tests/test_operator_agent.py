"""Tests for OperatorAgent decisions."""

from __future__ import annotations

from tbcrawl.agent.operator_agent import OperatorAgent
from tbcrawl.director.openrouter_director import LLMError


class FailingDirector:
    def generate_json(self, system_prompt: str, user_payload: dict) -> dict:
        raise LLMError("rate limit", status_code=429)


def test_operator_agent_backoff_on_429() -> None:
    agent = OperatorAgent(mode="operator", director=FailingDirector())
    snapshot = {
        "ui": {"inline": [[{"text": "A", "row": 0, "col": 0, "data": "x", "message_id": 1}]], "reply": []},
        "bundle": {"active_buttons_message_id": 1},
        "input_required": {"is_required": False, "candidates": []},
        "health": {},
        "crawl_state": {},
    }
    decision = agent.decide_snapshot(snapshot, allow_llm=True)
    assert decision is not None
    assert decision.action_type == "backoff_sleep"


def test_operator_agent_heuristic_fallback() -> None:
    agent = OperatorAgent(mode="assist", director=None)
    snapshot = {
        "ui": {"inline": [[{"text": "A", "row": 0, "col": 0, "data": "x", "message_id": 1}]], "reply": []},
        "bundle": {"active_buttons_message_id": 1},
        "input_required": {"is_required": False, "candidates": []},
        "health": {},
        "crawl_state": {},
    }
    decision = agent.decide_snapshot(snapshot, allow_llm=False)
    assert decision is not None
    assert decision.action_type == "click_inline"
