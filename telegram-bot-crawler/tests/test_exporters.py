"""Tests for export functions."""

import json
from pathlib import Path

import pytest
from tbcrawl.exporters import export_json, export_markdown
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
def populated_bot_map() -> BotMap:
    """Create a bot map with multiple nodes and edges."""
    metadata = CrawlMetadata(
        bot_username="test_bot",
        depth_limit=4,
        max_nodes=100,
        max_edges=500,
        max_actions=1000,
        strategy="bfs",
    )

    bot_map = BotMap(metadata=metadata)

    # Root node
    root = Node(
        id="root123abc",
        text="Welcome! Choose an option:",
        buttons=[
            [Button(text="Menu 1"), Button(text="Menu 2")],
            [Button(text="Help", url="https://help.example.com")],
        ],
        screen_type=ScreenType.MENU,
        example_path=[],
        media=MediaInfo(has_media=False),
    )
    bot_map.add_node(root)

    # Menu 1 node
    menu1 = Node(
        id="menu1abcd",
        text="You selected Menu 1. Enter your name:",
        buttons=[],
        screen_type=ScreenType.INPUT_REQUIRED,
        example_path=[Action(type=ActionType.CLICK, value="Menu 1")],
        media=MediaInfo(has_media=False),
    )
    bot_map.add_node(menu1)

    # Menu 2 node
    menu2 = Node(
        id="menu2efgh",
        text="Menu 2 content with photo",
        buttons=[[Button(text="Back")]],
        screen_type=ScreenType.MENU,
        example_path=[Action(type=ActionType.CLICK, value="Menu 2")],
        media=MediaInfo(has_media=True, types=["photo"]),
    )
    bot_map.add_node(menu2)

    # Edges
    bot_map.add_edge(
        Edge(
            from_node="root123abc",
            to_node="menu1abcd",
            action=Action(type=ActionType.CLICK, value="Menu 1"),
        )
    )
    bot_map.add_edge(
        Edge(
            from_node="root123abc",
            to_node="menu2efgh",
            action=Action(type=ActionType.CLICK, value="Menu 2"),
        )
    )

    return bot_map


class TestExportJson:
    """Tests for JSON export."""

    def test_creates_valid_json(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Exported JSON should be valid."""
        output_file = tmp_path / "bot_map.json"
        export_json(populated_bot_map, output_file)

        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "nodes" in data
        assert "edges" in data

    def test_metadata_content(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Metadata should contain correct info."""
        output_file = tmp_path / "bot_map.json"
        export_json(populated_bot_map, output_file)

        with open(output_file) as f:
            data = json.load(f)

        assert data["metadata"]["bot_username"] == "test_bot"
        assert data["metadata"]["strategy"] == "bfs"
        assert data["metadata"]["depth_limit"] == 4

    def test_nodes_content(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Nodes should be properly serialized."""
        output_file = tmp_path / "bot_map.json"
        export_json(populated_bot_map, output_file)

        with open(output_file) as f:
            data = json.load(f)

        nodes = data["nodes"]
        assert len(nodes) == 3
        assert "root123abc" in nodes

        root_node = nodes["root123abc"]
        assert root_node["screen_type"] == "menu"
        assert len(root_node["buttons"]) == 2

    def test_edges_content(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Edges should be properly serialized."""
        output_file = tmp_path / "bot_map.json"
        export_json(populated_bot_map, output_file)

        with open(output_file) as f:
            data = json.load(f)

        edges = data["edges"]
        assert len(edges) == 2

        edge = edges[0]
        assert "from" in edge
        assert "to" in edge
        assert "action" in edge

    def test_creates_parent_directories(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Should create parent directories if needed."""
        output_file = tmp_path / "nested" / "dir" / "bot_map.json"
        export_json(populated_bot_map, output_file)
        assert output_file.exists()


class TestExportMarkdown:
    """Tests for Markdown export."""

    def test_creates_markdown_file(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Should create markdown file."""
        output_file = tmp_path / "bot_map.md"
        export_markdown(populated_bot_map, output_file)
        assert output_file.exists()

    def test_contains_header(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Markdown should have header with bot name."""
        output_file = tmp_path / "bot_map.md"
        export_markdown(populated_bot_map, output_file)

        content = output_file.read_text(encoding="utf-8")
        assert "# Bot Map: @test_bot" in content

    def test_contains_summary(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Markdown should have summary section."""
        output_file = tmp_path / "bot_map.md"
        export_markdown(populated_bot_map, output_file)

        content = output_file.read_text(encoding="utf-8")
        assert "## Summary" in content
        assert "Screens Found" in content
        assert "3" in content  # 3 nodes

    def test_contains_screen_sections(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Each screen should have a section."""
        output_file = tmp_path / "bot_map.md"
        export_markdown(populated_bot_map, output_file)

        content = output_file.read_text(encoding="utf-8")
        assert "## Screens" in content
        assert "### Screen 1:" in content
        assert "### Screen 2:" in content
        assert "### Screen 3:" in content

    def test_contains_screen_types(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Screen types should be displayed."""
        output_file = tmp_path / "bot_map.md"
        export_markdown(populated_bot_map, output_file)

        content = output_file.read_text(encoding="utf-8")
        assert "Menu" in content
        assert "Input Required" in content

    def test_contains_buttons(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Buttons should be listed."""
        output_file = tmp_path / "bot_map.md"
        export_markdown(populated_bot_map, output_file)

        content = output_file.read_text(encoding="utf-8")
        assert "Menu 1" in content
        assert "Menu 2" in content

    def test_contains_transitions_table(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Transitions should be in a table."""
        output_file = tmp_path / "bot_map.md"
        export_markdown(populated_bot_map, output_file)

        content = output_file.read_text(encoding="utf-8")
        assert "## Transitions" in content
        assert "| From |" in content
        assert "| Action |" in content

    def test_url_buttons_are_links(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """URL buttons should be rendered as markdown links."""
        output_file = tmp_path / "bot_map.md"
        export_markdown(populated_bot_map, output_file)

        content = output_file.read_text(encoding="utf-8")
        assert "[Help](https://help.example.com)" in content

    def test_media_indicator(
        self, populated_bot_map: BotMap, tmp_path: Path
    ) -> None:
        """Media should be indicated."""
        output_file = tmp_path / "bot_map.md"
        export_markdown(populated_bot_map, output_file)

        content = output_file.read_text(encoding="utf-8")
        assert "**Media**:" in content
        assert "photo" in content
