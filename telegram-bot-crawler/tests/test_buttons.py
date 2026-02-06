"""Tests for button extraction."""

from __future__ import annotations

from tbcrawl.buttons import extract_buttons
from tbcrawl.models import ButtonKind


class StubButton:
    def __init__(self, text: str, url: str | None = None, data: bytes | None = None):
        self.text = text
        self.url = url
        self.data = data


class StubRow:
    def __init__(self, buttons: list[StubButton]):
        self.buttons = buttons


class ReplyInlineMarkup:
    def __init__(self, rows: list[StubRow]):
        self.rows = rows


class ReplyKeyboardMarkup:
    def __init__(self, rows: list[StubRow]):
        self.rows = rows


class FakeMessage:
    def __init__(self, reply_markup=None, buttons=None):
        self.reply_markup = reply_markup
        self.buttons = buttons


def test_extract_inline_buttons() -> None:
    msg = FakeMessage(
        reply_markup=ReplyInlineMarkup(
            [
                StubRow([StubButton("A", data=b"1"), StubButton("B", url="https://x")]),
            ]
        )
    )
    extraction = extract_buttons(msg)
    assert extraction.inline_count == 2
    assert extraction.reply_count == 0
    assert extraction.buttons[0][0].kind == ButtonKind.INLINE
    assert extraction.buttons[0][1].kind == ButtonKind.URL
    assert extraction.buttons[0][0].row == 0
    assert extraction.buttons[0][0].col == 0
    assert extraction.inline_rows[0][0]["row"] == 0
    assert extraction.inline_rows[0][0]["col"] == 0


def test_extract_reply_buttons() -> None:
    msg = FakeMessage(
        reply_markup=ReplyKeyboardMarkup(
            [StubRow([StubButton("One"), StubButton("Two")])]
        )
    )
    extraction = extract_buttons(msg)
    assert extraction.reply_count == 2
    assert extraction.inline_count == 0
    assert extraction.buttons[0][0].kind == ButtonKind.REPLY
    assert extraction.buttons[0][0].row == 0
    assert extraction.buttons[0][0].col == 0


def test_extract_from_message_buttons() -> None:
    msg = FakeMessage(
        reply_markup=None,
        buttons=[[StubButton("Call", data=b"cb")]],
    )
    extraction = extract_buttons(msg)
    assert extraction.inline_count == 1
    assert extraction.reply_count == 0
