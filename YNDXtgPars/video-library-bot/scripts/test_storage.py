from __future__ import annotations

import asyncio

from app.config import Settings
from app.services.yandex_disk_storage import YandexDiskStorage
from app.utils import join_disk_path


async def _main() -> None:
    settings = Settings()
    storage = YandexDiskStorage(settings)

    token_ok = await storage.check_token()
    print(f"token_ok={token_ok}")
    if not token_ok:
        return

    print(f"root_path={settings.yandex_disk_root}")
    entries = await storage.list_dir(settings.yandex_disk_root)
    print(f"root_entries={len(entries)}")
    for entry in entries[:10]:
        entry_type = entry.get("type")
        entry_path = entry.get("path")
        print(f"entry={entry_type}:{entry_path}")

    folders = await storage.list_folders(settings.yandex_disk_root)
    print(f"folders_found={len(folders)}")

    tmp_root = join_disk_path(settings.yandex_disk_root, "__tmp_test__")
    tmp_file = join_disk_path(tmp_root, "health.txt")
    try:
        await storage.create_dir(tmp_root)
        await storage.upload_text(tmp_file, "storage_test_ok")
        content = await storage.read_text(tmp_file)
        print(f"tmp_write_read_ok={content.strip() == 'storage_test_ok'}")
        await storage.delete(tmp_file, permanently=True)
        try:
            await storage.delete(tmp_root, permanently=True)
        except Exception:
            pass
    except Exception as exc:
        print(f"tmp_write_read_failed={exc}")
        print("read-only token or no write permissions")

    meta_path = None
    for folder in folders:
        candidate = f"{folder.rstrip('/')}/meta.json"
        if await storage.exists(candidate):
            meta_path = candidate
            break

    if not meta_path:
        print("meta.json not found under root")
        return

    meta = await storage.read_json(meta_path)
    print(f"meta_path={meta_path}")
    print("meta_json:")
    print(meta)


if __name__ == "__main__":
    asyncio.run(_main())
