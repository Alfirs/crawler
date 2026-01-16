from __future__ import annotations

from textwrap import dedent
from typing import TypedDict


class RewriteResult(TypedDict):
    hook: str
    body: str
    cta: str
    image_prompt: str
    translated_text: str


class LLMClient:
    """Wrapper for GPT-style model used to translate and adapt posts."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model
        # TODO: initialize OpenAI/Anthropic/etc. SDK client.

    def rewrite_post(self, raw_text_en: str) -> RewriteResult:
        """Translate Threads text to RU and craft metadata.

        Replace stubbed response with actual LLM call once wired.
        """

        prompt = dedent(
            f"""
            Translate the following Threads post to Russian using casual tone.
            Then craft:
            - hook: 120 chars max, attention-grabbing statement
            - body: 2-3 sentences summarizing implications for RU audience
            - cta: direct invitation to act or comment
            - image_prompt: English description for a cyberpunk/futuristic cover art
            Return JSON with keys hook, body, cta, image_prompt, translated_text.
            Source: {raw_text_en}
            """
        ).strip()
        # TODO: send prompt to LLM provider, parse JSON.
        _ = prompt
        return RewriteResult(
            hook="⚡️Будущее в твоём отделе",
            body="ИИ делит рутину и снимает нагрузку — главное, дать людям обучиться новым ролям.",
            cta="Расскажите, что автоматизируете в этом месяце?",
            image_prompt="Neon cyberpunk workspace, holographic dashboards, russian captions, cinematic lighting",
            translated_text="ИИ меняет процессы быстрее, чем регламенты успевают обновить.",
        )
