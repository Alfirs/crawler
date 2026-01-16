from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.config import Settings
from app.db import db_session, init_db
from app.jobs.scan_job import ScanJob
from app.models import VideoStatus
from app.services.catalog_service import CatalogService
from app.services.index_service import IndexService
from app.services.yandex_disk_storage import YandexDiskStorage
from app.utils import join_disk_path, normalize_disk_path


PLACEHOLDER_VIDEO = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41"


async def _ensure_write(storage: YandexDiskStorage, root: str) -> bool:
    test_path = join_disk_path(root, "write_test.txt")
    try:
        await storage.create_dir(root)
        await storage.upload_text(test_path, "edge_cases_ok")
        await storage.delete(test_path, permanently=True)
        return True
    except Exception as exc:
        print(f"write_check_failed={exc}")
        return False


async def _safe_delete(storage: YandexDiskStorage, path: str) -> None:
    try:
        await storage.delete(path, permanently=True)
    except Exception:
        pass


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
    cases_root = join_disk_path(root, "__tmp_cases__")

    if not await _ensure_write(storage, cases_root):
        print("SKIPPED: read-only token or no write permissions")
        return 0

    catalog = CatalogService(settings.db_path)
    scan_job = ScanJob(
        storage,
        catalog,
        settings.yandex_disk_root,
        stability_check_sec=0,
        auto_meta_mode="write",
    )

    failures: list[str] = []
    results: list[str] = []
    skipped: dict[str, str] = {}

    # Case A: no video
    case_a = join_disk_path(cases_root, "CaseA_NoVideo")
    try:
        await storage.create_dir(case_a)
        await storage.upload_text(join_disk_path(case_a, "summary.md"), "Summary only")
    except Exception as exc:
        skipped["CaseA"] = str(exc)

    # Case B: multiple videos
    case_b = join_disk_path(cases_root, "CaseB_MultipleVideos")
    try:
        await storage.create_dir(case_b)
        await storage.upload_file(join_disk_path(case_b, "one.mp4"), PLACEHOLDER_VIDEO)
        await storage.upload_file(join_disk_path(case_b, "two.mp4"), PLACEHOLDER_VIDEO)
        await storage.upload_text(
            join_disk_path(case_b, "summary.md"), "Summary for multiple"
        )
    except Exception as exc:
        skipped["CaseB"] = str(exc)

    # Case C: bad meta.json
    case_c = join_disk_path(cases_root, "CaseC_BadMeta")
    try:
        await storage.create_dir(case_c)
        await storage.upload_file(join_disk_path(case_c, "video.mp4"), PLACEHOLDER_VIDEO)
        await storage.upload_text(
            join_disk_path(case_c, "summary.md"), "Summary for bad meta"
        )
        await storage.upload_text(join_disk_path(case_c, "meta.json"), "{bad json")
    except Exception as exc:
        skipped["CaseC"] = str(exc)

    # Case D: root-level video
    root_video_name = "WeirdRoot_edgecase.mp4"
    root_video_path = join_disk_path(root, root_video_name)
    try:
        await _safe_delete(storage, root_video_path)
        await storage.upload_file(root_video_path, PLACEHOLDER_VIDEO)
    except Exception as exc:
        skipped["CaseD"] = str(exc)

    # Case E: broken encoding
    case_e = join_disk_path(cases_root, "CaseE_BadEncoding")
    try:
        await storage.create_dir(case_e)
        await storage.upload_file(join_disk_path(case_e, "video.mp4"), PLACEHOLDER_VIDEO)
        bad_bytes = "\u0422\u0435\u0441\u0442\u043e\u0432\u0430\u044f \u0441\u0442\u0440\u043e\u043a\u0430 cp1251".encode(
            "cp1251", errors="replace"
        )
        await storage.upload_file(join_disk_path(case_e, "summary.md"), bad_bytes)
    except Exception as exc:
        skipped["CaseE"] = str(exc)

    # Case F: long name with emoji
    long_name = "CaseF_" + ("ochen_dlinnoe_imya_" * 5) + "\U0001F642"
    case_f = join_disk_path(cases_root, long_name)
    try:
        await storage.create_dir(case_f)
        await storage.upload_file(join_disk_path(case_f, "video.mp4"), PLACEHOLDER_VIDEO)
        await storage.upload_text(join_disk_path(case_f, "summary.md"), "Long name summary")
    except Exception as exc:
        skipped["CaseF"] = str(exc)

    # Case G: deleted folder
    case_g = join_disk_path(cases_root, "CaseG_Delete")
    try:
        await storage.create_dir(case_g)
        await storage.upload_file(join_disk_path(case_g, "video.mp4"), PLACEHOLDER_VIDEO)
        await storage.upload_text(join_disk_path(case_g, "summary.md"), "Delete me")
    except Exception as exc:
        skipped["CaseG"] = str(exc)

    print("Running scan for edge cases...")
    try:
        await scan_job.run_once()
    except Exception as exc:
        print(f"scan_failed={exc}")
        return 1

    # Case A
    if "CaseA" in skipped:
        results.append(f"CaseA: SKIPPED ({skipped['CaseA']})")
    else:
        record_a = await catalog.get_video(normalize_disk_path(case_a))
        if not record_a or record_a.status != VideoStatus.ERROR or record_a.error_code != "NO_VIDEO":
            failures.append("CaseA: expected ERROR NO_VIDEO")
        results.append(
            f"CaseA: status={record_a.status.value if record_a else 'missing'} code={record_a.error_code if record_a else 'missing'}"
        )

    # Case B
    if "CaseB" in skipped:
        results.append(f"CaseB: SKIPPED ({skipped['CaseB']})")
    else:
        record_b = await catalog.get_video(normalize_disk_path(case_b))
        if not record_b or record_b.status != VideoStatus.ERROR or record_b.error_code != "MULTIPLE_VIDEOS":
            failures.append("CaseB: expected ERROR MULTIPLE_VIDEOS")
        results.append(
            f"CaseB: status={record_b.status.value if record_b else 'missing'} code={record_b.error_code if record_b else 'missing'}"
        )

    # Case C
    if "CaseC" in skipped:
        results.append(f"CaseC: SKIPPED ({skipped['CaseC']})")
    else:
        record_c = await catalog.get_video(normalize_disk_path(case_c))
        if not record_c or record_c.status != VideoStatus.ERROR or record_c.error_code != "BAD_META_JSON":
            failures.append("CaseC: expected ERROR BAD_META_JSON")
        results.append(
            f"CaseC: status={record_c.status.value if record_c else 'missing'} code={record_c.error_code if record_c else 'missing'}"
        )

    # Case D
    target_folder = join_disk_path(root, Path(root_video_name).stem)
    target_path = join_disk_path(target_folder, root_video_name)
    moved = False
    if "CaseD" in skipped:
        results.append(f"CaseD: SKIPPED ({skipped['CaseD']})")
    else:
        try:
            moved = await storage.exists(target_path)
        except Exception:
            moved = False
        if moved:
            results.append("CaseD: moved to folder")
        else:
            record_d = await catalog.get_video(normalize_disk_path(target_folder))
            if not record_d or record_d.error_code != "NO_PERMISSION_MOVE":
                failures.append("CaseD: expected move or ERROR NO_PERMISSION_MOVE")
            results.append(
                f"CaseD: status={record_d.status.value if record_d else 'missing'} code={record_d.error_code if record_d else 'missing'}"
            )

    # Case E
    if "CaseE" in skipped:
        results.append(f"CaseE: SKIPPED ({skipped['CaseE']})")
    else:
        record_e = await catalog.get_video(normalize_disk_path(case_e))
        if not record_e or record_e.status != VideoStatus.READY:
            failures.append("CaseE: expected READY with bad encoding summary")
        results.append(
            f"CaseE: status={record_e.status.value if record_e else 'missing'} code={record_e.error_code if record_e else 'missing'}"
        )

    # Case F
    if "CaseF" in skipped:
        results.append(f"CaseF: SKIPPED ({skipped['CaseF']})")
    else:
        record_f = await catalog.get_video(normalize_disk_path(case_f))
        if not record_f or record_f.status != VideoStatus.READY:
            failures.append("CaseF: expected READY for long/emoji name")
        results.append(
            f"CaseF: status={record_f.status.value if record_f else 'missing'} code={record_f.error_code if record_f else 'missing'}"
        )

    # Case G: delete and rescan
    if "CaseG" in skipped:
        results.append(f"CaseG: SKIPPED ({skipped['CaseG']})")
    else:
        index_service = IndexService(
            settings.db_path,
            settings.data_dir,
            storage,
            sim_threshold=settings.sim_threshold,
            lexical_boost=settings.lexical_boost,
        )
        await index_service.build_or_update_index()
        await _safe_delete(storage, case_g)
        await scan_job.run_once()
        await index_service.build_or_update_index()

        record_g = await catalog.get_video(normalize_disk_path(case_g))
        if not record_g or record_g.status != VideoStatus.DELETED:
            failures.append("CaseG: expected DELETED after removal")
        else:
            async with db_session(settings.db_path) as db:
                cursor = await db.execute(
                    "SELECT 1 FROM index_state WHERE video_id = ?",
                    (record_g.video_id,),
                )
                if await cursor.fetchone():
                    failures.append("CaseG: index_state not removed for DELETED")
        results.append(
            f"CaseG: status={record_g.status.value if record_g else 'missing'} code={record_g.error_code if record_g else 'missing'}"
        )

    for line in results:
        print(line)

    # Cleanup root-level video if still there
    await _safe_delete(storage, root_video_path)
    if moved:
        await _safe_delete(storage, target_folder)

    if failures:
        print(f"FAIL: {', '.join(failures)}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
