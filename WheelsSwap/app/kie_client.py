from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import tempfile
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class KieClientError(RuntimeError):
    """Raised when kie.ai responds with an error."""


class KieClient:
    """Async wrapper around kie.ai Seedream edit API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        timeout = httpx.Timeout(settings.kie_timeout_seconds)
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def edit_image_with_seedream(
        self,
        *,
        base_image_path: Path,
        wheel_reference_path: Path,
        prompt: str,
    ) -> bytes:
        """Upload assets, run nano-banana-pro edit using image_input and download the result."""

        logger.info("Uploading assets for Seedream edit")
        base_image_url = await self._upload_file(base_image_path)
        reference_url = await self._upload_file(wheel_reference_path)

        input_payload: dict[str, Any] = {
            "model": self.settings.seedream_model_name,
            "input": {
                "image_input": [base_image_url, reference_url],
                "prompt": prompt,
                "aspect_ratio": self.settings.render_aspect_ratio,
                "resolution": self.settings.render_resolution,
                "output_format": self.settings.render_output_format,
            },
        }

        endpoint = f"{self.settings.kie_base_url}/jobs/createTask"
        response = await self._client.post(endpoint, headers=self._headers(json_payload=True), json=input_payload)
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 200:
            raise KieClientError(f"kie.ai task creation failed: {body}")

        task_id = body["data"]["taskId"]
        logger.info("Seedream task %s created", task_id)
        result_url = await self._poll_task(task_id)
        download_url = await self._prepare_download_url(result_url)
        return await self._download_file(download_url)

    async def _upload_file(self, path: Path | None) -> str:
        if path is None:
            raise KieClientError("File path is required for upload")

        upload_endpoint = f"{self.settings.kie_upload_base_url}/api/file-stream-upload"
        data = {"uploadPath": self.settings.kie_upload_path, "fileName": path.name}
        files = {"file": (path.name, path.read_bytes(), "application/octet-stream")}
        response = await self._client.post(upload_endpoint, headers=self._headers(), data=data, files=files)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success") or not payload.get("data"):
            raise KieClientError(f"kie.ai upload failed: {payload}")
        file_info = payload["data"]
        file_url = file_info.get("fileUrl") or file_info.get("downloadUrl")
        if not file_url:
            logger.warning("kie.ai upload response without fileUrl: %s", payload)
            raise KieClientError("kie.ai upload API did not return fileUrl")
        return file_url

    async def _poll_task(self, task_id: str) -> str:
        endpoint = f"{self.settings.kie_base_url}/jobs/recordInfo"
        deadline = asyncio.get_event_loop().time() + self.settings.kie_poll_timeout

        while True:
            if asyncio.get_event_loop().time() > deadline:
                raise KieClientError("Timed out waiting for kie.ai task to finish")

            response = await self._client.get(endpoint, headers=self._headers(), params={"taskId": task_id})
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 200 or not payload.get("data"):
                raise KieClientError(f"kie.ai polling failed: {payload}")

            data = payload["data"]
            state = data.get("state")
            if state == "success":
                result_json = data.get("resultJson")
                if not result_json:
                    raise KieClientError("kie.ai finished without resultJson")
                parsed = json.loads(result_json)
                urls = parsed.get("resultUrls") or []
                if not urls:
                    raise KieClientError("kie.ai resultJson does not contain resultUrls")
                return urls[0]
            if state == "fail":
                fail_msg = data.get("failMsg") or "Seedream task failed"
                raise KieClientError(fail_msg)

            await asyncio.sleep(self.settings.kie_poll_interval)

    async def _prepare_download_url(self, result_url: str) -> str:
        endpoint = f"{self.settings.kie_base_url}/common/download-url"
        response = await self._client.post(
            endpoint, headers=self._headers(json_payload=True), json={"url": result_url}
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200 or not payload.get("data"):
            raise KieClientError(f"Failed to prepare download URL: {payload}")
        return payload["data"]

    async def _download_file(self, url: str) -> bytes:
        response = await self._client.get(url)
        response.raise_for_status()
        return response.content

    def _materialize(self, source: str | Path | bytes, suffix: str = "") -> tuple[Path, bool]:
        if isinstance(source, (str, Path)):
            return Path(source), False
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".bin")
        tmp.write(source)
        tmp.flush()
        tmp.close()
        return Path(tmp.name), True

    def _headers(self, *, json_payload: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.settings.kie_api_key}"}
        if json_payload:
            headers["Content-Type"] = "application/json"
        return headers
