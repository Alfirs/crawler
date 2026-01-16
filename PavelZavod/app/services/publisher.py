from app.models.draft_post import DraftPost


class Publisher:
    """Handles posting approved drafts to external platforms."""

    def publish_to_threads(self, draft: DraftPost) -> None:
        # TODO: implement Threads RU publishing logic
        print(f"[Threads] Published {draft.id}")

    def publish_to_tenchat(self, draft: DraftPost) -> None:
        # TODO: call TenChat API
        print(f"[TenChat] Published {draft.id}")

    def publish_to_telegram(self, draft: DraftPost, image_url: str | None = None) -> None:
        # TODO: call Telegram bot API with media
        print(f"[Telegram] Published {draft.id} with image={image_url}")
