from __future__ import annotations

from typing import Any

import httpx

from core.models import Idea, Product

_SYSTEM_PROMPT = (
    "You are a storyboard writer for short vertical ads (Reels/TikTok) that will be "
    "generated with SORA Storyboard. Always respond with concise scene descriptions "
    "using the format 'Scene N: ...' and limit the script to 3-5 scenes covering up to "
    "15 seconds total. Reference the provided product image as the hero object and "
    "describe actions, camera moves, and atmosphere for each scene."
)


class NeuroAPIClient:
    """Async client for the NeuroAPI (OpenAI-compatible) chat completions endpoint."""

    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://api.neuroapi.dev/v1",
        model: str = "gpt-5-mini",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate_script(self, product: Product, idea: Idea) -> str:
        """Generate a storyboard script for a given product/idea pair."""
        if not self.api_key:
            raise RuntimeError("NeuroAPI API key is not configured")

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": self._build_user_prompt(product, idea)},
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
        }

        timeout = httpx.Timeout(60.0, connect=30.0)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout) as client:
            response = await client.post("/chat/completions", headers=headers, json=payload)
        response.raise_for_status()

        data: Any = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Unexpected NeuroAPI response structure") from exc

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("NeuroAPI returned an empty script")
        return content.strip()

    def _build_user_prompt(self, product: Product, idea: Idea) -> str:
        description = product.short_description or "No additional description provided."
        return (
            f"Product: {product.title}\n"
            f"Description: {description}\n"
            f"Idea: {idea.text}\n\n"
            "Write a clear storyboard for a vertical video up to 15 seconds. "
            "Provide 3-5 numbered scenes (Scene 1:, Scene 2:, ...), each describing "
            "visuals, actions, and camera movement in one sentence."
        )
