from __future__ import annotations

import asyncio

from app.config import Settings
from app.services.seed_demo import seed_demo
from app.services.yandex_disk_storage import YandexDiskStorage


async def _main() -> None:
    settings = Settings()
    storage = YandexDiskStorage(settings)

    token_ok = await storage.check_token()
    print(f"token_ok={token_ok}")
    if not token_ok:
        print("ERROR: Yandex Disk token is invalid or missing")
        return

    result = await seed_demo(storage, settings, None)
    print(f"seed_demo_result={result}")


if __name__ == "__main__":
    asyncio.run(_main())
