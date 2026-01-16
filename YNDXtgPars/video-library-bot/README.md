# Video Library Bot

Telegram bot that scans a Yandex.Disk video library, stores a local catalog in SQLite, and supports semantic search via txtai.

## Features

- Automatic scanning with **auto-meta** when `meta.json` is missing
- **Auto-organize** files dropped in the root (Pattern B -> Pattern A)
- **Auto-summary** (`summary.md`) from folder name/title.txt + description.txt
- Incremental txtai indexing with fingerprint tracking
- Optional transcription (faster-whisper) with graceful fallback
- Cloud-side `library_index.json` for easy inspection
- Telegram UX with top-1 suggestion and “show more” option
- Fail-safe error handling with diagnostics and /health endpoint

## Yandex.Disk Layouts

Pattern A (preferred):
```
/VideoLibrary/<AnyFolderTitle>/
    video.mp4
    description.txt    (optional)
    title.txt          (optional)
    summary.md         (auto-generated if missing)
    transcript.txt/.vtt (optional)
    meta.json          (auto-generated if missing)
```

Pattern B (common):
```
/VideoLibrary/<title>.mp4
```
The scanner moves it into `disk:/VideoLibrary/<title>/` automatically.

## Auto-Meta and Auto-Summary

- If `meta.json` exists, it is treated as the source of truth and is updated with new text files.
- If `meta.json` is missing and `AUTO_META_MODE=write`, the scanner writes a fresh `meta.json`.
- If `summary.md` is missing, it is created from:
  - `title.txt` (first non-empty line), or folder name
  - `description.txt` if present

## Cloud Index File

After each scan, the bot uploads:
```
disk:/VideoLibrary/library_index.json
```
This is a readable JSON list with:
`video_id`, `title`, `video_path`, `texts`, `summary_excerpt`, `fingerprint`, `updated_at`, `status`.

## Quick Start (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
notepad .env
python -m app.main
```

## Create Yandex.Disk Folder

1. Open https://disk.yandex.ru and create a `VideoLibrary` folder in the root.
2. Set `YANDEX_DISK_ROOT` to `disk:/VideoLibrary` (or `/VideoLibrary`).

## Configuration (.env)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | yes | - | Telegram bot token from @BotFather |
| `YANDEX_DISK_OAUTH_TOKEN` | yes | - | OAuth token for Yandex.Disk API |
| `ADMIN_USER_IDS` | yes | - | Comma-separated list of admin Telegram user IDs |
| `YANDEX_DISK_ROOT` | no | `/VideoLibrary` | Root folder to scan on Yandex.Disk |
| `SCAN_INTERVAL_SEC` | no | `300` | Interval between automatic scans (seconds) |
| `STABILITY_CHECK_SEC` | no | `30` | Delay for file stability check |
| `SIM_THRESHOLD` | no | `0.30` | Similarity threshold for “low confidence” warning |
| `LEXICAL_BOOST` | no | `0.15` | Small re-rank boost for title/token matches |
| `TOP_K` | no | `3` | Number of search results to show |
| `TELEGRAM_SEND_MAX_MB` | no | `45` | Max file size for direct Telegram upload |
| `DATA_DIR` | no | `./data` | Directory for SQLite database and txtai index |
| `AUTO_META_MODE` | no | `write` | `write` / `derive` / `off` |
| `ENABLE_TRANSCRIPTION` | no | `0` | Enable optional transcription loop (0/1) |
| `TRANSCRIBE_MODEL` | no | `small` | faster-whisper model name |
| `SEED_SAMPLE_VIDEO_PATH` | no | empty | Local path to sample video used by seed_demo |
| `CHAOS_MODE` | no | `0` | Enable chaos testing (0/1) |
| `CHAOS_RATE` | no | `0.15` | Chaos injection probability (0..1) |

`MAX_TELEGRAM_UPLOAD_MB` is still accepted for backward compatibility.

## Bot Commands

### User
- `/start`
- `/help`
- Send any text to search the library

### Admin
- `/admin_status` - status + last scan/index errors
- `/reindex` - rebuild the index
- `/reindex <video_id>` - reindex a single video
- `/add_video` - upload via Telegram
- `/selftest` - run a standard search test
- `/seed_demo` - create demo folders + run selftest
- `/health` - quick health snapshot

## Optional Transcription

1. Install ffmpeg and add it to `PATH`
2. Install faster-whisper:
   ```powershell
   pip install faster-whisper
   ```
3. Set `ENABLE_TRANSCRIPTION=1`

If dependencies are missing, the bot logs a warning and continues without transcription.

## Testing Scripts

```powershell
python -m scripts.test_storage
python -m scripts.seed_demo
python -m scripts.test_search
python -m scripts.smoke_user_queries
python -m scripts.edge_cases
python -m scripts.chaos_smoke
python -m scripts.audit_all
.\check.ps1
```

`scripts.chaos_smoke` enables CHAOS_MODE for test runs only.

## Architecture

```
scan_job.run_once() -> Scans Yandex.Disk, auto-meta/summary, writes library_index.json
index_service.build_or_update_index() -> Indexes READY videos into txtai
index_service.search(query) -> SearchResponse with top-k results
Telegram bot -> Shows top-1 + “show more”
```

## Data Storage

- **SQLite database**: `DATA_DIR/video_library.db`
  - `videos` - Video metadata and status
  - `chunks` - Text chunks for search
  - `index_state` - Fingerprints for incremental indexing
  - `telegram_cache` - Cached Telegram file IDs
  - `scan_log` - Scan history

- **txtai index**: `DATA_DIR/txtai_index/`
- **Index version**: `DATA_DIR/txtai_index/index_version.json`

## Notes

- Videos are READY if a stable video and at least one stable text exist.
- Large videos (> `TELEGRAM_SEND_MAX_MB`) are shared via public Yandex.Disk links.
- The scanner skips indexing while a file is still uploading (stability check).
- Library root files with video extensions are auto-moved into a folder.

## Manual E2E Checklist

1) `python -m app.main`  
2) In Telegram: `/seed_demo`  
3) `/selftest`  
4) Queries:
   - "дай мне видео с руинами"
   - "разбор мазей"
   - "как пользоваться пером"
5) Tap “Отправить” and verify file/link delivery
