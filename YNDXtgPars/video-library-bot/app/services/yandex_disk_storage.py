from __future__ import annotations

import asyncio
import json
import logging
import random
from pathlib import Path, PurePosixPath
from typing import Any

import httpx

from app.config import Settings
from app.services.storage_base import StorageBase, StorageError


class YandexDiskStorage(StorageBase):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger("video_library_bot.storage")
        self._base_url = "https://cloud-api.yandex.net/v1/disk"
        self._timeout = httpx.Timeout(30.0, connect=10.0)
        self._download_timeout = httpx.Timeout(30.0, read=None)
        self._max_retries = 3
        self._retry_base_delay = 0.6
        self._chaos_mode = settings.chaos_mode
        self._chaos_rate = settings.chaos_rate
        if self._chaos_mode:
            self._timeout = httpx.Timeout(10.0, connect=5.0)
            self._download_timeout = httpx.Timeout(10.0, read=20.0)
            self._max_retries = 2
            self._retry_base_delay = 0.2

    async def get_quota(self) -> dict[str, int]:
        """Get disk quota info: total_space, used_space, free_space (in bytes)."""
        data = await self._request_json(
            "GET", "", allowed_statuses={200}, operation="get_quota"
        )
        total = data.get("total_space", 0)
        used = data.get("used_space", 0)
        return {
            "total_space": total,
            "used_space": used,
            "free_space": total - used,
        }

    async def list_dir(self, path: str) -> list[dict[str, Any]]:
        return await self._list_dir(path)

    async def list_folders(self, root_path: str) -> list[str]:
        root = self._normalize_path(root_path)
        folders: list[str] = []
        queue = [root]
        seen: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            folders.append(current)
            for item in await self.list_dir(current):
                if item.get("type") != "dir":
                    continue
                path = self._normalize_path(item.get("path") or "")
                if not path or self._should_skip_folder(path):
                    continue
                queue.append(path)
        return folders

    async def read_json(self, path: str) -> dict:
        text = await self._download_text(path, operation="read_json")
        try:
            return json.loads(text)
        except ValueError as exc:
            raise ValueError(f"Invalid JSON in {self._normalize_path(path)}") from exc

    async def read_text(self, path: str) -> str:
        return await self._download_text(path, operation="read_text")

    async def get_meta(self, path: str) -> dict:
        data = await self._get_resource(path, fields="size,modified,md5,sha256")
        if not data:
            raise FileNotFoundError(path)
        meta = {}
        for key in ("size", "modified", "md5", "sha256"):
            if key in data and data[key] is not None:
                meta[key] = data[key]
        etag = meta.get("sha256") or meta.get("md5")
        if etag:
            meta["etag"] = etag
        return meta

    async def download_file(
        self, path: str, local_path: str, max_bytes: int | None = None
    ) -> None:
        href = await self._get_download_href(path, operation="download_file")
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_suffix(target.suffix + ".tmp")
        try:
            await self._download_with_retry(
                href,
                tmp_path,
                path=self._normalize_path(path),
                max_bytes=max_bytes,
            )
            tmp_path.replace(target)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    async def publish_link(self, path: str) -> str:
        normalized = self._normalize_path(path)
        await self._request_json(
            "PUT",
            "/resources/publish",
            params={"path": normalized},
            allowed_statuses={200, 201, 202, 409},
            operation="publish_link",
            path=normalized,
        )
        data = await self._get_resource(normalized, fields="public_url")
        public_url = data.get("public_url") if data else None
        if not public_url:
            raise StorageError(
                method="publish_link",
                url=f"{self._base_url}/resources",
                path=normalized,
                status_code=0,
                response_text="public_url missing",
                hint="resource not published or unavailable",
            )
        return public_url

    async def exists(self, path: str) -> bool:
        data = await self._get_resource(path, fields="path")
        return data is not None

    async def create_dir(self, path: str) -> None:
        normalized = self._normalize_path(path)
        await self._request_json(
            "PUT",
            "/resources",
            params={"path": normalized},
            allowed_statuses={201, 409},
            operation="create_dir",
            path=normalized,
        )

    async def upload_text(self, path: str, content: str) -> None:
        normalized = self._normalize_path(path)
        href = await self._get_upload_href(normalized, operation="upload_text")
        response = await self._request_with_retry(
            "PUT", href, content=content.encode("utf-8"), operation="upload_text", path=normalized
        )
        if response.status_code not in {200, 201, 202}:
            raise self._raise_storage_error("upload_text", href, normalized, response)

    async def upload_file(
        self, remote_path: str, local_path_or_bytes: str | bytes | bytearray
    ) -> None:
        normalized = self._normalize_path(remote_path)
        href = await self._get_upload_href(normalized, operation="upload_file")
        payload: bytes | None = None
        if isinstance(local_path_or_bytes, (bytes, bytearray)):
            payload = bytes(local_path_or_bytes)
        else:
            target = Path(local_path_or_bytes)
            if not target.exists():
                raise FileNotFoundError(local_path_or_bytes)
        if payload is not None:
            response = await self._request_with_retry(
                "PUT", href, content=payload, operation="upload_file", path=normalized
            )
        else:
            # Read file into bytes - can't pass sync file object to AsyncClient
            file_bytes = target.read_bytes()
            response = await self._request_with_retry(
                "PUT", href, content=file_bytes, operation="upload_file", path=normalized
            )
        if response.status_code not in {200, 201, 202}:
            raise self._raise_storage_error("upload_file", href, normalized, response)

    async def move(self, src: str, dst: str, overwrite: bool = False) -> None:
        src_norm = self._normalize_path(src)
        dst_norm = self._normalize_path(dst)
        if not overwrite:
            dst_norm = await self._resolve_move_target(src_norm, dst_norm)
        await self._request_json(
            "POST",
            "/resources/move",
            params={
                "from": src_norm,
                "path": dst_norm,
                "overwrite": str(overwrite).lower(),
            },
            allowed_statuses={201, 202, 204, 409},
            operation="move",
            path=f"{src_norm} -> {dst_norm}",
        )

    async def delete(self, path: str, permanently: bool = False) -> None:
        normalized = self._normalize_path(path)
        await self._request_json(
            "DELETE",
            "/resources",
            params={
                "path": normalized,
                "permanently": str(permanently).lower(),
            },
            allowed_statuses={202, 204, 404},
            operation="delete",
            path=normalized,
        )

    async def check_token(self) -> bool:
        try:
            await self._request_json("GET", "", allowed_statuses={200}, operation="check_token")
        except StorageError as exc:
            if exc.status_code in {401, 403}:
                return False
            raise
        return True

    def _normalize_path(self, path: str) -> str:
        normalized = (path or "").strip().replace("\\", "/")
        if normalized.startswith("/"):
            normalized = normalized[1:]
        if normalized.startswith("disk:"):
            normalized = normalized[len("disk:") :]
            if normalized.startswith("/"):
                normalized = normalized[1:]
        if not normalized:
            return "disk:/"
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if len(normalized) > 1:
            normalized = normalized.rstrip("/")
        return f"disk:{normalized}"

    def _strip_disk_prefix(self, path: str) -> str:
        normalized = (path or "").strip().replace("\\", "/")
        if normalized.startswith("/"):
            normalized = normalized[1:]
        if normalized.startswith("disk:"):
            normalized = normalized[len("disk:") :]
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return normalized

    def _should_skip_folder(self, path: str) -> bool:
        name = PurePosixPath(self._strip_disk_prefix(path)).name
        return name in {"_index", ".index"}

    async def _list_dir(self, path: str) -> list[dict[str, Any]]:
        if self._maybe_chaos_list_dir(path):
            return []
        items: list[dict[str, Any]] = []
        limit = 1000
        offset = 0
        while True:
            data = await self._request_json(
                "GET",
                "/resources",
                params={
                    "path": self._normalize_path(path),
                    "limit": limit,
                    "offset": offset,
                    "fields": "_embedded.items.path,_embedded.items.name,_embedded.items.type",
                },
                allowed_statuses={200, 404},
                operation="list_dir",
                path=path,
            )
            if not data or "error" in data:
                return []
            embedded = data.get("_embedded") or {}
            batch = embedded.get("items") or []
            items.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return items

    async def _get_resource(self, path: str, fields: str | None = None) -> dict[str, Any] | None:
        params = {"path": self._normalize_path(path)}
        if fields:
            params["fields"] = fields
        data = await self._request_json(
            "GET",
            "/resources",
            params=params,
            allowed_statuses={200, 404},
            operation="get_resource",
            path=path,
        )
        if not data or "error" in data:
            return None
        return data

    async def _get_download_href(self, path: str, operation: str) -> str:
        data = await self._request_json(
            "GET",
            "/resources/download",
            params={"path": self._normalize_path(path)},
            operation=operation,
            path=path,
        )
        href = data.get("href") if isinstance(data, dict) else None
        if not href:
            raise RuntimeError(f"Download link not available for {path}")
        return href

    async def _get_upload_href(self, path: str, operation: str) -> str:
        data = await self._request_json(
            "GET",
            "/resources/upload",
            params={"path": self._normalize_path(path), "overwrite": "true"},
            operation=operation,
            path=path,
        )
        href = data.get("href") if isinstance(data, dict) else None
        if not href:
            raise RuntimeError(f"Upload link not available for {path}")
        return href

    async def _download_text(self, path: str, operation: str) -> str:
        href = await self._get_download_href(path, operation=operation)
        response = await self._request_with_retry(
            "GET", href, operation=operation, path=self._normalize_path(path)
        )
        if response.status_code != 200:
            raise self._raise_storage_error(operation, href, self._normalize_path(path), response)
        return response.content.decode("utf-8", errors="replace")

    @staticmethod
    def _raise_storage_error(
        operation: str, url: str, path: str, response: httpx.Response
    ) -> StorageError:
        hint = YandexDiskStorage._error_hint(response.status_code)
        return StorageError(
            method=operation,
            url=url,
            path=path,
            status_code=response.status_code,
            response_text=response.text,
            hint=hint,
        )

    @staticmethod
    def _error_hint(status_code: int) -> str:
        if status_code in {401, 403}:
            return "check OAuth token and permissions"
        if status_code == 404:
            return "path not found"
        if status_code == 409:
            return "conflict or already exists"
        if status_code == 429:
            return "rate limited; retry later"
        if status_code >= 500:
            return "storage service error"
        return "request failed"

    async def _request_json(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        allowed_statuses: set[int] | None = None,
        operation: str = "request",
        path: str | None = None,
    ) -> dict[str, Any]:
        token = self._settings.yandex_disk_oauth_token
        if not token:
            raise RuntimeError("YANDEX_DISK_OAUTH_TOKEN is not set")
        if allowed_statuses is None:
            allowed_statuses = {200}
        url = f"{self._base_url}{endpoint}"
        response = await self._request_with_retry(
            method,
            url,
            params=params,
            headers={"Authorization": f"OAuth {token}"},
            operation=operation,
            path=path or str(params),
        )
        if response.status_code not in allowed_statuses:
            error = self._raise_storage_error(
                operation, url, path or str(params), response
            )
            if error.status_code == 404:
                self._logger.info(str(error))
            else:
                self._logger.error(str(error))
            raise error
        if response.status_code == 204:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        operation: str,
        path: str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                self._maybe_chaos(operation, path)
                async with httpx.AsyncClient(
                    timeout=self._timeout, follow_redirects=True, trust_env=False
                ) as client:
                    response = await client.request(method, url, **kwargs)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self._max_retries:
                    await self._sleep_backoff(attempt)
                    continue
                return response
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                await self._sleep_backoff(attempt)
        if last_exc:
            raise StorageError(
                method=operation,
                url=url,
                path=path or "",
                status_code=0,
                response_text=str(last_exc),
                hint="network error; retry later",
            ) from last_exc
        raise StorageError(
            method=operation,
            url=url,
            path=path or "",
            status_code=0,
            response_text="request failed",
            hint="network error; retry later",
        )

    async def _sleep_backoff(self, attempt: int) -> None:
        delay = self._retry_base_delay * (2 ** (attempt - 1))
        jitter = random.uniform(0, 0.2)
        await asyncio.sleep(delay + jitter)

    async def _download_with_retry(
        self,
        href: str,
        target: Path,
        path: str,
        max_bytes: int | None,
    ) -> None:
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                self._maybe_chaos("download_file", path)
                async with httpx.AsyncClient(
                    timeout=self._download_timeout,
                    follow_redirects=True,
                    trust_env=False,
                ) as client:
                    async with client.stream("GET", href) as response:
                        if response.status_code in {429, 500, 502, 503, 504}:
                            if attempt < self._max_retries:
                                await self._sleep_backoff(attempt)
                                continue
                        if response.status_code != 200:
                            raise self._raise_storage_error(
                                "download_file", href, path, response
                            )
                        total = 0
                        with target.open("wb") as output:
                            async for chunk in response.aiter_bytes():
                                output.write(chunk)
                                total += len(chunk)
                                if max_bytes is not None and total > max_bytes:
                                    raise StorageError(
                                        method="download_file",
                                        url=href,
                                        path=path,
                                        status_code=413,
                                        response_text="download exceeds max_bytes",
                                        hint="file too large",
                                    )
                        return
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    await self._sleep_backoff(attempt)
                    continue
                break
        if last_exc:
            raise StorageError(
                method="download_file",
                url=href,
                path=path,
                status_code=0,
                response_text=str(last_exc),
                hint="network error; retry later",
            ) from last_exc

    def _maybe_chaos(self, operation: str, path: str | None = None) -> None:
        if not self._chaos_mode:
            return
        if random.random() >= self._chaos_rate:
            return
        choice = random.choice(("connect", "timeout", "storage_429", "storage_500"))
        if choice == "connect":
            raise httpx.ConnectError("chaos connect error", request=None)
        if choice == "timeout":
            raise httpx.ReadTimeout("chaos timeout", request=None)
        if choice == "storage_429":
            raise StorageError(
                method=operation,
                url=f"{self._base_url}/chaos",
                path=path or "",
                status_code=429,
                response_text="chaos injected 429",
                hint="rate limited; retry later",
            )
        raise StorageError(
            method=operation,
            url=f"{self._base_url}/chaos",
            path=path or "",
            status_code=500,
            response_text="chaos injected 500",
            hint="storage service error",
        )

    def _maybe_chaos_list_dir(self, path: str) -> bool:
        if not self._chaos_mode:
            return False
        if random.random() < self._chaos_rate * 0.2:
            self._logger.warning(
                "chaos list_dir empty",
                extra={"path": self._normalize_path(path)},
            )
            return True
        return False

    async def _resolve_move_target(self, src: str, dst: str) -> str:
        try:
            if not await self.exists(dst):
                return dst
        except Exception:
            return dst

        dst_path = PurePosixPath(self._strip_disk_prefix(dst))
        stem = dst_path.stem
        suffix = dst_path.suffix
        parent = dst_path.parent
        for idx in range(1, 6):
            candidate_name = f"{stem}_{idx}{suffix}"
            candidate = self._normalize_path(str(parent / candidate_name))
            try:
                if not await self.exists(candidate):
                    return candidate
            except Exception:
                break
        return dst
