"""Pytest configuration and fixtures."""

import pytest
from tbcrawl.models import (
    Action,
    ActionType,
    BotMap,
    Button,
    CrawlMetadata,
    Edge,
    MediaInfo,
    Node,
    ScreenType,
)


@pytest.fixture
def sample_button() -> Button:
    """Create a sample button."""
    return Button(text="Click me")


@pytest.fixture
def sample_url_button() -> Button:
    """Create a sample URL button."""
    return Button(text="Visit site", url="https://example.com")


@pytest.fixture
def sample_action() -> Action:
    """Create a sample action."""
    return Action(type=ActionType.CLICK, value="Menu")


@pytest.fixture
def sample_media_info() -> MediaInfo:
    """Create sample media info."""
    return MediaInfo(has_media=True, types=["photo"])


@pytest.fixture
def sample_node() -> Node:
    """Create a sample node."""
    return Node(
        id="abc12345",
        text="Welcome to the bot! Choose an option:",
        buttons=[
            [Button(text="Option 1"), Button(text="Option 2")],
            [Button(text="Help", url="https://help.example.com")],
        ],
        screen_type=ScreenType.MENU,
        example_path=[Action(type=ActionType.SEND_TEXT, value="/start")],
        media=MediaInfo(has_media=False, types=[]),
    )


@pytest.fixture
def sample_edge() -> Edge:
    """Create a sample edge."""
    return Edge(
        from_node="abc12345",
        to_node="def67890",
        action=Action(type=ActionType.CLICK, value="Option 1"),
    )


@pytest.fixture
def sample_metadata() -> CrawlMetadata:
    """Create sample metadata."""
    return CrawlMetadata(
        bot_username="test_bot",
        depth_limit=4,
        max_nodes=100,
        max_edges=500,
        max_actions=1000,
        strategy="bfs",
    )


@pytest.fixture
def sample_bot_map(sample_metadata: CrawlMetadata, sample_node: Node) -> BotMap:
    """Create a sample bot map."""
    bot_map = BotMap(metadata=sample_metadata)
    bot_map.add_node(sample_node)
    return bot_map
