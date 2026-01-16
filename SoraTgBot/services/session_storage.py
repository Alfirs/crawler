from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable

from core.dto import ProductDraft, ProductFormData, UserBatchConfig
from services.app_settings import AppSettingsService
from services.sqlite_storage import SQLiteStorage


class UserSessionStorage:
    """
    Hybrid storage for user drafts.

    - The current (in-progress) form lives in RAM so the FSM flow stays simple.
    - Completed drafts and batch configs are persisted via SQLiteStorage,
      which keeps data safe across bot restarts.
    """

    def __init__(
        self,
        sqlite_storage: SQLiteStorage,
        settings_service: AppSettingsService | None = None,
    ) -> None:
        self._sqlite = sqlite_storage
        self._settings_service = settings_service
        self._forms: Dict[int, ProductFormData] = {}

    # ----------------------- form lifecycle (in-memory) -----------------------

    def start_form(self, user_id: int) -> ProductFormData:
        form = ProductFormData()
        self._forms[user_id] = form
        return form

    def get_current_form(self, user_id: int) -> ProductFormData | None:
        return self._forms.get(user_id)

    def update_current_form(self, user_id: int, **fields) -> ProductFormData:
        form = self._forms.setdefault(user_id, ProductFormData())
        for key, value in fields.items():
            if hasattr(form, key):
                setattr(form, key, value)
        return form

    def discard_current_form(self, user_id: int) -> None:
        self._forms.pop(user_id, None)

    async def complete_form(self, user_id: int) -> ProductDraft:
        form = self._forms.get(user_id)
        if form is None:
            raise ValueError("Нет активной карточки товара.")
        if not form.image_path:
            raise ValueError("Сначала отправь фотографию товара.")
        if not form.description:
            raise ValueError("Описание товара не заполнено.")

        draft = await self._sqlite.add_product_draft(
            user_id=user_id,
            description=form.description,
            image_path=form.image_path,
            image_file_id=form.image_file_id,
        )
        self.discard_current_form(user_id)
        return draft

    # ----------------------------- persisted drafts ---------------------------

    async def create_draft_from_photo(
        self,
        user_id: int,
        *,
        description: str | None,
        image_path: Path,
        image_file_id: str | None,
    ) -> ProductDraft:
        return await self._sqlite.add_product_draft(
            user_id=user_id,
            description=description,
            image_path=image_path,
            image_file_id=image_file_id,
        )

    async def update_draft_description(self, draft_id: str, description: str | None) -> None:
        await self._sqlite.update_product_draft(draft_id, description=description)

    async def get_drafts(self, user_id: int) -> list[ProductDraft]:
        return await self._sqlite.list_product_drafts(user_id)

    async def consume_drafts(self, user_id: int) -> list[ProductDraft]:
        return await self._sqlite.consume_product_drafts(user_id)

    # ----------------------------- batch config ------------------------------

    async def set_generation_count(self, user_id: int, count: int) -> UserBatchConfig:
        default_count = 1
        if self._settings_service:
            default_count = await self._settings_service.get_default_generation_count()
        config = await self._sqlite.get_batch_config(user_id, default_generation_count=default_count)
        ideas = config.ideas
        return await self._sqlite.set_batch_config(
            user_id=user_id,
            generation_count=count,
            ideas=ideas,
        )

    async def set_ideas(self, user_id: int, ideas: Iterable[str]) -> UserBatchConfig:
        default_count = 1
        if self._settings_service:
            default_count = await self._settings_service.get_default_generation_count()
        config = await self._sqlite.get_batch_config(user_id, default_generation_count=default_count)
        return await self._sqlite.set_batch_config(
            user_id=user_id,
            generation_count=config.generation_count,
            ideas=list(ideas),
        )

    async def get_config(self, user_id: int) -> UserBatchConfig:
        default_count = 1
        if self._settings_service:
            default_count = await self._settings_service.get_default_generation_count()
        return await self._sqlite.get_batch_config(user_id, default_generation_count=default_count)


def create_session_storage(
    sqlite_storage: SQLiteStorage,
    settings_service: AppSettingsService | None = None,
) -> UserSessionStorage:
    return UserSessionStorage(sqlite_storage, settings_service)
