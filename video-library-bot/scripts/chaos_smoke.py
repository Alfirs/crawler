from __future__ import annotations

import asyncio
import os
import sys
import time

from app.config import Settings
from app.db import init_db
from app.jobs.scan_job import ScanJob
from app.services.catalog_service import CatalogService
from app.services.index_service import IndexService
from app.services.yandex_disk_storage import YandexDiskStorage


QUERIES = ["руина", "перо", "разбор мазей"]


async def _run_cycle(
    storage: YandexDiskStorage,
    catalog: CatalogService,
    index_service: IndexService,
    settings: Settings,
    label: str,
) -> int:
    errors = 0
    scan_result = None
    index_updated = False
    scan_job = ScanJob(
        storage,
        catalog,
        settings.yandex_disk_root,
        stability_check_sec=0,
        auto_meta_mode=settings.auto_meta_mode,
    )

    try:
        scan_result = await scan_job.run_once()
        print(f"{label}: scan ok")
    except Exception as exc:
        errors += 1
        print(f"{label}: scan error {exc}")

    try:
        index_updated = await index_service.build_or_update_index()
        status = "ok" if index_updated else "skipped"
        print(f"{label}: index {status}")
    except Exception as exc:
        errors += 1
        print(f"{label}: index error {exc}")

    ready_count = 0
    total_scanned = 0
    if isinstance(scan_result, dict):
        ready_count = int(scan_result.get("ready_count", 0) or 0)
        total_scanned = int(scan_result.get("total_folders_scanned", 0) or 0)
    allow_empty = not index_updated and (ready_count == 0 or total_scanned == 0 or not scan_result)

    for query in QUERIES:
        try:
            response = await index_service.search(query, max(settings.top_k, 3))
            found = len(response.results)
            print(f"{label}: query '{query}' found={found}")
            if found == 0 and not allow_empty:
                errors += 1
                print(f"{label}: FAIL empty results without empty-scan guard")
        except Exception as exc:
            errors += 1
            print(f"{label}: query '{query}' error {exc}")

    return errors


async def _main() -> int:
    os.environ["CHAOS_MODE"] = "1"
    os.environ.setdefault("CHAOS_RATE", "0.3")

    settings = Settings()
    await init_db(settings.db_path)

    storage = YandexDiskStorage(settings)
    token_ok = await storage.check_token()
    print(f"token_ok={token_ok}")
    if not token_ok:
        print("ERROR: Yandex Disk token is invalid or missing")
        return 0

    catalog = CatalogService(settings.db_path)
    index_service = IndexService(
        settings.db_path,
        settings.data_dir,
        storage,
        sim_threshold=settings.sim_threshold,
        lexical_boost=settings.lexical_boost,
    )

    chaos_errors = 0
    cycles = 0
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        cycles += 1
        chaos_errors += await _run_cycle(
            storage, catalog, index_service, settings, f"chaos_cycle_{cycles}"
        )
        await asyncio.sleep(2)

    print(f"chaos_cycles={cycles} chaos_errors={chaos_errors}")

    # Recovery cycle without chaos
    os.environ["CHAOS_MODE"] = "0"
    clean_settings = Settings()
    clean_storage = YandexDiskStorage(clean_settings)
    clean_catalog = CatalogService(clean_settings.db_path)
    clean_index = IndexService(
        clean_settings.db_path,
        clean_settings.data_dir,
        clean_storage,
        sim_threshold=clean_settings.sim_threshold,
        lexical_boost=clean_settings.lexical_boost,
    )

    recovery_errors = await _run_cycle(
        clean_storage, clean_catalog, clean_index, clean_settings, "recovery"
    )

    counts = await clean_catalog.get_status_counts()
    total = sum(counts.values())
    if total > 0 and counts.get("READY", 0) == 0:
        print("FAIL: no READY videos after recovery")
        return 1

    if recovery_errors:
        print("FAIL: recovery cycle had errors")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
