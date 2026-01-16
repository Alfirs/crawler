from __future__ import annotations

import asyncio
import json
import sys

from app.config import Settings
from app.db import init_db
from app.jobs.scan_job import ScanJob
from app.services.catalog_service import CatalogService
from app.services.index_service import IndexService
from app.services.yandex_disk_storage import YandexDiskStorage
from app.utils import join_disk_path


QUERIES = [
    ("руина", "руин"),
    ("руины", "руин"),
    ("руинами", "руин"),
    ("дай мне видео с руинами", "руин"),
    ("разбор мазей", "маз"),
    ("покажи мне разборы мазей", "маз"),
    ("перо", "перо"),
    ("как пользоваться пером", "перо"),
]


async def _main() -> int:
    settings = Settings()
    await init_db(settings.db_path)

    storage = YandexDiskStorage(settings)

    token_ok = await storage.check_token()
    print(f"token_ok={token_ok}")
    if not token_ok:
        print("ERROR: Yandex Disk token is invalid or missing")
        return 0

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

    index_path = join_disk_path(settings.yandex_disk_root, "library_index.json")
    try:
        index_text = await storage.read_text(index_path)
        index_data = json.loads(index_text)
        if not isinstance(index_data, dict):
            raise ValueError("library_index.json must be an object")
        if index_data.get("schema_version") != 1:
            raise ValueError("library_index.json schema_version mismatch")
        items = index_data.get("items")
        if not isinstance(items, list):
            raise ValueError("library_index.json items must be a list")
        print("library_index.json: OK")
    except Exception as exc:
        print(f"library_index.json: FAIL ({exc})")
        return 1

    counts = await catalog.get_status_counts()
    print(f"Video counts: {counts}")
    total = sum(counts.values())
    if total == 0:
        print("library empty")
        return 0

    index_service = IndexService(
        settings.db_path,
        settings.data_dir,
        storage,
        sim_threshold=settings.sim_threshold,
        lexical_boost=settings.lexical_boost,
    )

    print("Building index...")
    await index_service.build_or_update_index()
    index_size = await index_service.index_size()
    print(f"Index size: {index_size} chunks")

    failures = []
    for query, expected in QUERIES:
        response = await index_service.search(query, max(settings.top_k, 3))
        print(f"\nQuery: {query}")
        print(f"  results: {len(response.results)}")
        print(f"  low_confidence: {response.low_confidence}")
        if response.results:
            top = response.results[0]
            print(f"  top1: {top.title} ({top.score:.3f})")
            snippet = top.snippet or ""
            if len(snippet) > 120:
                snippet = f"{snippet[:120]}..."
            if snippet:
                print(f"  snippet: {snippet}")
            has_expected = expected in (top.title or "").lower()
            status = "OK" if has_expected else "FAIL"
            print(f"  check: top1 contains '{expected}' -> {status}")
            if not has_expected:
                failures.append(f"top1 missing '{expected}' for query '{query}'")
        else:
            print(f"  check: top1 contains '{expected}' -> FAIL")
            failures.append(f"top1 missing '{expected}' for query '{query}'")

    if failures:
        print(f"FAIL: {', '.join(failures)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
