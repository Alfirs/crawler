"""Targeted crawler logic tests."""

from __future__ import annotations

from pathlib import Path

from tbcrawl.checkpoint import CrawlCheckpoint, load_checkpoint, save_checkpoint
from tbcrawl.config import CrawlerConfig
from tbcrawl.crawler import BotCrawler
from tbcrawl.models import Action, ActionType, Button, ButtonKind, MediaInfo, Node, ScreenType


def _config(tmp_path: Path) -> CrawlerConfig:
    return CrawlerConfig(
        bot_username="test_bot",
        api_id=1,
        api_hash="hash",
        output_dir=tmp_path,
        use_llm=False,
    )


def test_action_dedupe_includes_row_col_data(tmp_path: Path) -> None:
    crawler = BotCrawler(_config(tmp_path))
    node = Node(
        id="node123",
        text="Buttons",
        buttons=[
            [
                Button(text="Same", kind=ButtonKind.INLINE, row=0, col=0, data="a"),
                Button(text="Same", kind=ButtonKind.INLINE, row=0, col=1, data="b"),
            ]
        ],
        screen_type=ScreenType.MENU,
        media=MediaInfo(),
        buttons_message_id=10,
    )
    actions = crawler._actions_for_node(node)
    assert len(actions) == 2
    assert actions[0].row != actions[1].row or actions[0].col != actions[1].col


def test_input_candidates_branching_heuristics(tmp_path: Path) -> None:
    crawler = BotCrawler(_config(tmp_path))
    node = Node(id="n1", text="Укажите ставку пошлины, %", screen_type=ScreenType.INPUT_REQUIRED)
    candidates = crawler._input_candidates_with_reasons(node)
    values = [value for value, _ in candidates[:3]]
    assert values == ["5", "10", "15"]

    node = Node(id="n2", text="Введите 10-значный код ТН ВЭД", screen_type=ScreenType.INPUT_REQUIRED)
    candidates = crawler._input_candidates_with_reasons(node)
    values = [value for value, _ in candidates[:3]]
    assert values == ["9027901000", "6109100000", "4202221000"]


def test_loop_detection_bans_action(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cfg.loop_repeat_threshold = 2
    crawler = BotCrawler(cfg)
    action = Action(type=ActionType.CLICK, value="A", row=0, col=0, data="x")
    action_key = crawler._action_key(action, message_id=1)
    crawler._register_action_result("node1", action_key, "node1")
    crawler._register_action_result("node1", action_key, "node1")
    assert action_key in crawler._action_bans.get("node1", set())


def test_checkpoint_roundtrip(tmp_path: Path) -> None:
    checkpoint = CrawlCheckpoint(
        visited_signatures=["a", "b"],
        actions_taken=10,
        queue=[{"node_id": "n1", "path": [], "depth": 1}],
        current_path=[],
        action_bans={"n1": ["k1"]},
        action_attempts={"n1": {"k1": 2}},
        action_last_result={"n1": {"k1": "n2"}},
        action_repeat_counts={"n1": {"k1": 1}},
        last_signature="n2",
        same_signature_repeat=1,
        last_actions=[],
        last_start_action_index=5,
    )
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, checkpoint)
    loaded = load_checkpoint(path)
    assert loaded is not None
    assert loaded.actions_taken == 10
    assert loaded.visited_signatures == ["a", "b"]
