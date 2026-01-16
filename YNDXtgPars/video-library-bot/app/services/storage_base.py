from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import re
from urllib.parse import urlsplit, urlunsplit
from typing import Optional, Union


@dataclass(frozen=True)
class StorageError(RuntimeError):
    method: str
    url: str
    path: str
    status_code: int
    response_text: str
    hint: str | None = None

    def __str__(self) -> str:
        safe_url = _sanitize_url(self.url)
        safe_body = _sanitize_text(self.response_text)
        hint = f" hint={self.hint}" if self.hint else ""
        return (
            f"StorageError {self.method} {safe_url} path={self.path} "
            f"status={self.status_code} body={safe_body}{hint}"
        )


def _sanitize_url(url: str) -> str:
    if not url:
        return ""
    redacted = re.sub(
        r"(?i)(token|access_token|oauth|authorization)=([^&]+)",
        r"\1=***",
        url,
    )
    try:
        parts = urlsplit(redacted)
    except ValueError:
        return redacted
    if parts.scheme and parts.netloc:
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return redacted


def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(
        r"(?i)(token|access_token|oauth|authorization)\\s*[:=]\\s*([\\w\\-]+)",
        r"\1=***",
        text,
    )


class StorageBase(ABC):
    @abstractmethod
    async def list_dir(self, path: str) -> list[dict]:
        """List directory entries for the given path."""

    @abstractmethod
    async def list_folders(self, root_path: str) -> list[str]:
        """Return all folders under the root path (recursive)."""

    @abstractmethod
    async def read_json(self, path: str) -> dict:
        """Read a JSON file from storage and return its contents."""

    @abstractmethod
    async def read_text(self, path: str) -> str:
        """Read a text file from storage and return its contents."""

    @abstractmethod
    async def get_meta(self, path: str) -> dict:
        """Return file metadata such as size, modified, and hashes."""

    @abstractmethod
    async def download_file(
        self, path: str, local_path: str, max_bytes: int | None = None
    ) -> None:
        """Download a file to local storage."""

    @abstractmethod
    async def publish_link(self, path: str) -> str:
        """Publish a file and return a public URL."""

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Return True if the path exists in storage."""

    @abstractmethod
    async def create_dir(self, path: str) -> None:
        """Create a directory (idempotent)."""

    @abstractmethod
    async def upload_text(self, path: str, content: str) -> None:
        """Upload a text file."""

    @abstractmethod
    async def upload_file(self, remote_path: str, local_path_or_bytes: Union[str, bytes, bytearray]) -> None:
        """Upload a local file or bytes to storage."""

    @abstractmethod
    async def move(self, src: str, dst: str, overwrite: bool = False) -> None:
        """Move or rename a file/folder."""

    @abstractmethod
    async def delete(self, path: str, permanently: bool = False) -> None:
        """Delete a file or folder."""
