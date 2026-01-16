from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class SoraClient:
    """Async client for interacting with the Kie.ai Sora 2 job API."""

    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://api.kie.ai/api/v1",
        create_task_path: str = "/jobs/createTask",
        model: str = "sora-2-image-to-video",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.create_task_path = create_task_path
        self.model = model

    async def generate_video(
        self,
        storyboard: str,
        image_url: str | None,
        *,
        aspect_ratio: str = "portrait",
        n_frames: str = "15",
        remove_watermark: bool = True,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        """Submit a storyboard + image to Sora 2 for video generation."""
        if not self.api_key:
            raise RuntimeError("Kie.ai API key is not configured")
        if not image_url:
            raise ValueError("Sora 2 image-to-video requires a public image_url")

        prompt = f"Storyboard: {' '.join(line.strip() for line in storyboard.splitlines() if line.strip())}"
        input_payload: dict[str, Any] = {
            "prompt": prompt,
            "image_urls": [image_url],
            "aspect_ratio": aspect_ratio,
            "n_frames": n_frames,
            "remove_watermark": remove_watermark,
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "input": input_payload,
        }
        if callback_url:
            payload["callBackUrl"] = callback_url

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}{self.create_task_path}",
                headers=headers,
                json=payload,
            )
        response.raise_for_status()

        data: Any = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Unexpected Kie.ai Sora response structure")
        return data

    async def get_task_details(self, task_id: str | None, record_id: str | None = None) -> dict[str, Any]:
        """Fetch status/details for a previously created task."""
        if not self.api_key:
            raise RuntimeError("Kie.ai API key is not configured")
        if not task_id:
            raise ValueError("task_id is required for status polling")

        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/jobs/recordInfo",
                headers=headers,
                params={"taskId": task_id},
            )
        response.raise_for_status()

        data: Any = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Unexpected Kie.ai Sora response structure")
        return data

    async def download_file(self, url: str, target_path: Path) -> Path:
        """Download a remote file (video) to disk."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with target_path.open("wb") as file_handle:
                    async for chunk in response.aiter_bytes():
                        file_handle.write(chunk)
        return target_path
