from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.domain.rates import RatesConfig, RatesStore
from app.flow.detectors import InputDetector, LogHints
from app.flow.engine import FlowEngine
from app.flow.loader import Action, ActionType, BotMap, Button, Edge, MediaInfo, Node, ScreenType
from app.storage.models import SessionState


def _rates_store() -> RatesStore:
    return RatesStore(path=Path("rates.yaml"), rates=RatesConfig())


def test_click_transition() -> None:
    node_a = Node(
        id="a",
        text="Root",
        buttons=[[Button(text="Next")]],
        screen_type=ScreenType.MENU,
        example_path=[],
        media=MediaInfo(),
        created_at=datetime.utcnow(),
    )
    node_b = Node(
        id="b",
        text="Done",
        buttons=[],
        screen_type=ScreenType.TERMINAL,
        example_path=[],
        media=MediaInfo(),
        created_at=datetime.utcnow(),
    )
    edge = Edge(
        from_node="a",
        to_node="b",
        action=Action(type=ActionType.CLICK, value="Next"),
        created_at=datetime.utcnow(),
    )
    bot_map = BotMap(metadata={}, nodes={"a": node_a, "b": node_b}, edges=[edge])
    detector = InputDetector(LogHints())
    engine = FlowEngine(
        bot_map=bot_map,
        detector=detector,
        rates_store=_rates_store(),
        default_keyboard_mode="inline",
        root_node_id="a",
    )
    session = SessionState(user_id=1, current_node_id="a")
    response = engine.handle_action(session, ActionType.CLICK, "Next")
    assert response.session.current_node_id == "b"
    assert response.rendered.text == "Done"
