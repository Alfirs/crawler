"""Tests for Pydantic models."""



from tbcrawl.models import (
    Action,
    ActionType,
    BotMap,
    Button,
    CrawlMetadata,
    Edge,
    MediaInfo,
    Node,
    RawLogEntry,
    ScreenType,
)


class TestButton:
    """Tests for Button model."""

    def test_simple_button(self) -> None:
        """Button with just text."""
        btn = Button(text="Click me")
        assert btn.text == "Click me"
        assert btn.url is None
        assert not btn.is_url_button()
        assert btn.row is None
        assert btn.col is None

    def test_url_button(self) -> None:
        """Button with URL."""
        btn = Button(text="Visit", url="https://example.com")
        assert btn.text == "Visit"
        assert btn.url == "https://example.com"
        assert btn.is_url_button()


class TestAction:
    """Tests for Action model."""

    def test_click_action(self) -> None:
        """Click action."""
        action = Action(type=ActionType.CLICK, value="Button")
        assert action.type == ActionType.CLICK
        assert action.value == "Button"
        assert action.row is None
        assert action.col is None

    def test_send_text_action(self) -> None:
        """Send text action."""
        action = Action(type=ActionType.SEND_TEXT, value="/start")
        assert action.type == ActionType.SEND_TEXT
        assert action.value == "/start"

    def test_serialization(self) -> None:
        """Action should serialize correctly."""
        action = Action(type=ActionType.CLICK, value="Test")
        data = action.model_dump()
        assert data["type"] == "click"
        assert data["value"] == "Test"


class TestMediaInfo:
    """Tests for MediaInfo model."""

    def test_no_media(self) -> None:
        """Default is no media."""
        media = MediaInfo()
        assert not media.has_media
        assert media.types == []

    def test_with_media(self) -> None:
        """Media with types."""
        media = MediaInfo(has_media=True, types=["photo", "document"])
        assert media.has_media
        assert "photo" in media.types


class TestNode:
    """Tests for Node model."""

    def test_minimal_node(self) -> None:
        """Node with minimal data."""
        node = Node(id="test123", text="Hello")
        assert node.id == "test123"
        assert node.text == "Hello"
        assert node.screen_type == ScreenType.TERMINAL
        assert node.buttons == []
        assert node.example_path == []
        assert node.buttons_message_id is None

    def test_node_with_buttons(self, sample_node: Node) -> None:
        """Node with buttons."""
        assert len(sample_node.buttons) == 2
        assert len(sample_node.buttons[0]) == 2

    def test_get_clickable_buttons(self, sample_node: Node) -> None:
        """Get only clickable (non-URL) buttons."""
        clickable = sample_node.get_clickable_buttons()
        assert len(clickable) == 2
        assert all(not btn.is_url_button() for btn in clickable)

    def test_get_url_buttons(self, sample_node: Node) -> None:
        """Get only URL buttons."""
        url_buttons = sample_node.get_url_buttons()
        assert len(url_buttons) == 1
        assert url_buttons[0].text == "Help"


class TestEdge:
    """Tests for Edge model."""

    def test_edge_creation(self) -> None:
        """Create edge with alias."""
        edge = Edge(
            **{
                "from": "node1",
                "to": "node2",
            },
            action=Action(type=ActionType.CLICK, value="Next"),
        )
        assert edge.from_node == "node1"
        assert edge.to_node == "node2"

    def test_edge_json_serialization(self, sample_edge: Edge) -> None:
        """Edge should serialize with 'from' and 'to' keys."""
        data = sample_edge.model_dump_json_safe()
        assert "from" in data
        assert "to" in data
        assert data["from"] == "abc12345"


class TestCrawlMetadata:
    """Tests for CrawlMetadata model."""

    def test_metadata_defaults(self) -> None:
        """Metadata has sensible defaults."""
        meta = CrawlMetadata(
            bot_username="test",
            depth_limit=4,
            max_nodes=100,
            max_edges=500,
            max_actions=1000,
            strategy="bfs",
        )
        assert meta.started_at is not None
        assert meta.completed_at is None
        assert meta.nodes_discovered == 0


class TestBotMap:
    """Tests for BotMap model."""

    def test_add_node(self, sample_bot_map: BotMap) -> None:
        """Adding a node."""
        new_node = Node(id="new123", text="New screen")
        added = sample_bot_map.add_node(new_node)
        assert added
        assert sample_bot_map.has_node("new123")
        assert sample_bot_map.metadata.nodes_discovered == 2

    def test_add_duplicate_node(self, sample_bot_map: BotMap, sample_node: Node) -> None:
        """Duplicate nodes should not be added."""
        added = sample_bot_map.add_node(sample_node)
        assert not added

    def test_add_edge(self, sample_bot_map: BotMap, sample_edge: Edge) -> None:
        """Adding an edge."""
        added = sample_bot_map.add_edge(sample_edge)
        assert added
        assert len(sample_bot_map.edges) == 1

    def test_is_at_limit_nodes(self, sample_metadata: CrawlMetadata) -> None:
        """Check node limit."""
        bot_map = BotMap(metadata=sample_metadata)

        # Add nodes up to limit
        for i in range(100):
            bot_map.add_node(Node(id=f"node_{i}", text=f"Screen {i}"))

        assert bot_map.is_at_limit()

    def test_edge_exists(self, sample_bot_map: BotMap, sample_edge: Edge) -> None:
        """Check edge existence."""
        sample_bot_map.add_edge(sample_edge)

        assert sample_bot_map.edge_exists(
            "abc12345",
            Action(type=ActionType.CLICK, value="Option 1"),
        )
        assert not sample_bot_map.edge_exists(
            "abc12345",
            Action(type=ActionType.CLICK, value="Other"),
        )


class TestRawLogEntry:
    """Tests for RawLogEntry model."""

    def test_to_jsonl(self) -> None:
        """Convert to JSONL line."""
        entry = RawLogEntry(
            event_type="test_event",
            data={"key": "value"},
        )
        jsonl = entry.to_jsonl()

        assert '"event_type": "test_event"' in jsonl
        assert '"key": "value"' in jsonl
        assert jsonl.count("\n") == 0  # Single line

    def test_unicode_in_jsonl(self) -> None:
        """Unicode should be preserved."""
        entry = RawLogEntry(
            event_type="message",
            data={"text": "Привет мир"},
        )
        jsonl = entry.to_jsonl()

        assert "Привет мир" in jsonl
