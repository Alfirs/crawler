from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(slots=True)
class ThreadPost:
    """Simplified representation of a Threads post."""

    id: str
    url: str
    text: str
    likes: int
    reposts: int
    created_at: datetime


class ThreadsClient:
    """Client responsible for fetching top Threads posts.

    Replace with real API/parser when credentials are available.
    """

    def __init__(self) -> None:
        # TODO: accept API credentials or session here.
        ...

    def fetch_top_threads(self, topic: str, limit: int = 5) -> Sequence[ThreadPost]:
        """Return mocked top posts for the supplied topic."""

        now = datetime.utcnow()
        return [
            ThreadPost(
                id=f"{topic}-{i}",
                url=f"https://threads.net/t/{topic}-{i}",
                text=f"{topic.title()} trend {i}: AI reshapes teams.",
                likes=500 + i * 25,
                reposts=80 + i * 10,
                created_at=now,
            )
            for i in range(1, limit + 1)
        ]
