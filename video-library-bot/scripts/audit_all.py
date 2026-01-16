from __future__ import annotations

import asyncio
import json
import sys

from app.config import Settings
from app.db import db_session, init_db
from app.jobs.scan_job import ScanJob
from app.main import _build_admin_status
from app.services.catalog_service import CatalogService
from app.services.index_service import IndexService
from app.services.seed_demo import DEMO_ITEMS, seed_demo
from app.services.yandex_disk_storage import YandexDiskStorage
from app.utils import join_disk_path, normalize_disk_path


REQUIRED_QUERIES = [
    ("руина", "руин"),
    ("разбор мазей", "маз"),
    ("перо", "перо"),
    ("дай мне видео с руинами", "руин"),
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
        return 1

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

    index_path = join_disk_path(settings.yandex_disk_root, "library_index.json")
    try:
        index_text = await storage.read_text(index_path)
        index_data = json.loads(index_text)
        if not isinstance(index_data, dict):
            raise ValueError("library_index.json must be an object")
        if index_data.get("schema_version") != 1:
            raise ValueError("library_index.json schema_version mismatch")
        if not isinstance(index_data.get("items"), list):
            raise ValueError("library_index.json items must be a list")
        print("library_index.json: OK")
    except Exception as exc:
        print(f"library_index.json: FAIL ({exc})")
        return 1

    failures: list[str] = []
    for query, expected in REQUIRED_QUERIES:
        response = await index_service.search(query, max(settings.top_k, 3))
        found = len(response.results)
        print(f"Query '{query}': found={found} low_confidence={response.low_confidence}")
        if found == 0:
            failures.append(query)
            continue
        if expected and expected not in response.results[0].title.lower():
            failures.append(f"{query} (top1 missing '{expected}')")

    counts = await catalog.get_status_counts()
    last_scan = "unknown"
    last_index = "unknown"
    async with db_session(settings.db_path) as db:
        cursor = await db.execute("SELECT scanned_at FROM scan_log ORDER BY id DESC LIMIT 1")
        row = await cursor.fetchone()
        if row:
            last_scan = row["scanned_at"]
        cursor = await db.execute("SELECT MAX(indexed_at) AS last_index FROM index_state")
        row = await cursor.fetchone()
        if row and row["last_index"]:
            last_index = row["last_index"]

    recent_errors = await catalog.list_recent_errors(limit=5)
    status_text = _build_admin_status(
        counts=counts,
        index_size=await index_service.index_size(),
        last_scan=last_scan,
        last_index=last_index,
        last_error="нет",
        last_scan_duration=None,
        last_index_duration=None,
        last_scan_error="нет",
        last_index_error="нет",
        recent_errors=recent_errors,
    )
    if counts.get("ERROR", 0) > 0 and "Последние ошибки" not in status_text:
        failures.append("admin_status missing error section")

    if failures:
        print(f"FAIL: {', '.join(failures)}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
