from __future__ import annotations

import asyncio
import sys

from app.config import Settings
from app.db import init_db
from app.jobs.scan_job import ScanJob
from app.services.catalog_service import CatalogService
from app.services.index_service import IndexService
from app.services.seed_demo import DEMO_ITEMS, seed_demo
from app.services.yandex_disk_storage import YandexDiskStorage
from app.utils import join_disk_path, normalize_disk_path


REQUIRED_QUERIES = [
    ("руина", None),
    ("разбор мазей", None),
    ("дай мне видео с руинами", None),
    ("как пользоваться пером", "перо"),
]


async def _needs_seed(storage: YandexDiskStorage, root: str) -> bool:
    for item in DEMO_ITEMS:
        folder = join_disk_path(root, item["folder"])
        try:
            if await storage.exists(folder):
                return False
        except Exception:
            continue
    return True


async def _main() -> int:
    settings = Settings()
    await init_db(settings.db_path)

    storage = YandexDiskStorage(settings)
    token_ok = await storage.check_token()
    print(f"token_ok={token_ok}")
    if not token_ok:
        print("ERROR: Yandex Disk token is invalid or missing")
        return 0

    root = normalize_disk_path(settings.yandex_disk_root)
    if await _needs_seed(storage, root):
        print("Seeding demo library...")
        result = await seed_demo(storage, settings, None)
        print(f"seed_demo_result={result}")

    catalog = CatalogService(settings.db_path)
    scan_job = ScanJob(
        storage,
        catalog,
        settings.yandex_disk_root,
        stability_check_sec=0,
        auto_meta_mode=settings.auto_meta_mode,
    )

    print("Running scan...")
    await scan_job.run_once()

    index_service = IndexService(
        settings.db_path,
        settings.data_dir,
        storage,
        sim_threshold=settings.sim_threshold,
        lexical_boost=settings.lexical_boost,
    )

    print("Building index...")
    await index_service.build_or_update_index()

    failures = []
    for query, expected in REQUIRED_QUERIES:
        response = await index_service.search(query, settings.top_k)
        found = len(response.results)
        print(f"Query '{query}': found={found} low_confidence={response.low_confidence}")
        if found == 0:
            failures.append(query)
            continue
        if expected:
            title = response.results[0].title.lower()
            if expected not in title:
                failures.append(f"{query} (top1 missing '{expected}')")

    if failures:
        print(f"FAIL: no results for {', '.join(failures)}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
