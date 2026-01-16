#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeeLark Reels Poster — GUI utility for scheduling Instagram Reels tasks via GeeLark Open API.

Updates (Aug 2025)
- Added AppId + ApiKey authentication headers (no Bearer token required).
- Multi‑device posting: accept a list and/or numeric ranges of Cloud Phone IDs; automatic round‑robin assignment.
- Backwards compatible: per‑row CSV `id` still overrides; single default ID also supported.
- Local files upload supported (getUrl + PUT) for live posting.

Highlights
- Modular service-provider architecture: easily add TikTok / YouTube modules later.
- Pick a folder with videos, a CSV file with per-video captions, and set start date/time + interval (minutes).
- Optional posting progression per day, e.g. "1:5, 2:10, 3:10" (day → posts/day) or JSON "[5,10,12]".
- Dry‑run preview to validate schedule before sending real API requests.
- Exports the planned schedule to CSV.

Requirements (install):
    pip install PySide6 requests python-dateutil tzdata

CSV mapping format (UTF‑8 / UTF‑8‑SIG):
filename,description,name,remark,id,video_url
video1.mp4,"Your caption #1",,,,
video2.mp4,"Your caption #2",My Task,Optional remark,557536075321468390,
video3.mp4,"Your caption #3 (will use default cloud phone id)",,,,
# If video_url is provided (https://...), the file path is ignored and no uploader is required.

Notes
- Authentication: provide AppId and ApiKey (headers `AppId` and `ApiKey`). Token/Bearer remains optional.
- The API expects scheduleAt as a Unix timestamp (seconds, UTC). The UI uses your local timezone and converts.
- One video per task. (The API supports <=10 per task; extend TaskPayload if you want multi‑video posts.)
"""
from __future__ import annotations

import csv
import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from dateutil import tz
import json
from pathlib import Path
import re
import sys
import traceback
import random
from typing import Dict, List, Optional, Set, Tuple, Any

import requests
from PySide6 import QtWidgets, QtGui

APP_TITLE = "Upload-Post Reels Poster"
UPLOAD_POST_DEFAULT_BASE = "https://api.upload-post.com"
UPLOAD_VIDEO_ENDPOINT = "/api/upload"
UPLOAD_STATUS_ENDPOINT = "/api/uploadposts/status"
MAX_DESCRIPTION = 2200
MAX_NAME = 128
MAX_REMARK = 200

def clamp_text_for_api(text: str, limit: int) -> str:
    t = (text or "").strip()
    byte_limit = limit * 4  # allow full-length UTF-8 captions (e.g., Cyrillic at 2-3 bytes per char)
    if len(t) <= limit and len(t.encode("utf-8")) <= byte_limit:
        return t
    # Trim to the requested character limit first.
    t = t[:limit]
    # Further reduce if the UTF-8 byte length still exceeds the expanded threshold.
    while len(t.encode("utf-8")) > byte_limit and len(t) > 0:
        t = t[:-1]
    return t


SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".webm"}

TRACE_LOG_PATH = Path("logs/upload_post_trace.log")

def parse_upload_post_response(text: str) -> Dict[str, Optional[Any]]:
    info: Dict[str, Optional[Any]] = {
        "success": None,
        "message": None,
        "request_id": None,
        "results": None,
        "usage": None,
    }
    try:
        data = json.loads(text)
    except Exception:
        return info
    if isinstance(data, dict):
        info["success"] = data.get("success")
        info["message"] = data.get("message") or data.get("error") or data.get("detail")
        info["request_id"] = data.get("request_id") or data.get("requestId")
        info["results"] = data.get("results")
        info["usage"] = data.get("usage")
    return info

def append_trace_log(entry: Dict[str, Any]) -> None:
    try:
        TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

# ----------------------------
# Data models
# ----------------------------
@dataclass
class VideoRow:
    filename: str
    description: str
    name: Optional[str] = None
    remark: Optional[str] = None
    user: Optional[str] = None  # Explicit upload user override
    video_url: Optional[str] = None  # If present, skip upload/resolve


@dataclass
class TaskPayload:
    name: Optional[str]
    remark: Optional[str]
    scheduleAt: int  # UTC epoch seconds
    id: str  # upload user
    description: str
    video: List[str]  # list of paths/URLs (length 1 here)
    platforms: List[str] = dataclasses.field(default_factory=list)
    title_overrides: Dict[str, str] = dataclasses.field(default_factory=dict)
    description_overrides: Dict[str, str] = dataclasses.field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)


@dataclass
class ScheduledItem:
    local_dt: datetime
    video_path_or_url: str
    payload: TaskPayload
    source_filename: str


# ----------------------------
# Provider base / registry
# ----------------------------
class ProviderError(Exception):
    pass


class BaseProvider:
    key: str = "base"
    label: str = "Base"

    def __init__(self, api_base: Optional[str] = None, api_key: Optional[str] = None):
        self.api_base = (api_base or UPLOAD_POST_DEFAULT_BASE).rstrip("/")
        self.api_key = (api_key or "").strip()
        self.session = requests.Session()

    def submit(self, scheduled: ScheduledItem) -> Tuple[int, str]:
        raise NotImplementedError


class UploadPostProvider(BaseProvider):
    key = "upload_post"
    label = "Upload-Post"

    SUPPORTED_DEFAULT_PLATFORM = "instagram"

    @staticmethod
    def _guess_mime(path: Path) -> str:
        ext = path.suffix.lower()
        return {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".m4v": "video/x-m4v",
            ".avi": "video/x-msvideo",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
            ".wmv": "video/x-ms-wmv",
            ".flv": "video/x-flv",
            ".mpeg": "video/mpeg",
            ".mpg": "video/mpeg",
            ".3gp": "video/3gpp",
        }.get(ext, "application/octet-stream")

    def submit(self, scheduled: ScheduledItem) -> Tuple[int, str]:
        if not self.api_key:
            raise ProviderError("API key is required for Upload-Post.")

        payload = scheduled.payload
        user = (payload.id or "").strip()
        if not user:
            raise ProviderError("Upload user is not specified (payload.id).")

        platforms = payload.platforms or [self.SUPPORTED_DEFAULT_PLATFORM]
        form_fields: List[Tuple[str, str]] = [("user", user)]
        for platform in platforms:
            if platform:
                form_fields.append(("platform[]", platform))

        title = payload.name or Path(scheduled.source_filename).stem
        form_fields.append(("title", title))

        if payload.description:
            form_fields.append(("description", payload.description))

        if payload.title_overrides:
            for platform, value in payload.title_overrides.items():
                if value:
                    form_fields.append((f"{platform}_title", value))

        if payload.description_overrides:
            for platform, value in payload.description_overrides.items():
                if value:
                    form_fields.append((f"{platform}_description", value))

        if payload.scheduleAt:
            try:
                dt = datetime.fromtimestamp(payload.scheduleAt, tz=timezone.utc)
                iso = dt.isoformat().replace("+00:00", "Z")
                form_fields.append(("scheduled_date", iso))
            except Exception:
                pass

        video_source = ''
        if payload.video:
            video_source = payload.video[0]
        elif scheduled.video_path_or_url:
            video_source = scheduled.video_path_or_url

        if not video_source:
            raise ProviderError("Video source path or URL is empty.")

        is_remote = bool(re.match(r"^https?://", str(video_source), re.IGNORECASE))
        url = f"{self.api_base}{UPLOAD_VIDEO_ENDPOINT}"
        headers = {"Authorization": f"Apikey {self.api_key}"}

        try:
            if is_remote:
                form_fields.append(("video", str(video_source)))
                resp = self.session.post(
                    url,
                    headers=headers,
                    data=form_fields,
                    timeout=90,
                )
            else:
                path_obj = Path(video_source)
                if not path_obj.exists():
                    raise ProviderError(f"Video file not found: {path_obj}")
                mime = self._guess_mime(path_obj)
                with path_obj.open("rb") as f:
                    files = [("video", (path_obj.name, f, mime))]
                    resp = self.session.post(
                        url,
                        headers=headers,
                        data=form_fields,
                        files=files,
                        timeout=300,
                    )
        except requests.RequestException as e:
            raise ProviderError(str(e))

        return resp.status_code, resp.text


class ProviderRegistry:
    _providers = {
        UploadPostProvider.key: UploadPostProvider,
    }
    _aliases = {
        'instagram': UploadPostProvider.key,
        'tiktok': UploadPostProvider.key,
    }

    @classmethod
    def create(cls, key: str, **kwargs) -> BaseProvider:
        real_key = cls._aliases.get(key, key)
        if real_key not in cls._providers:
            raise ValueError(f"Unknown provider: {key}")
        return cls._providers[real_key](**kwargs)

    @classmethod
    def options(cls) -> List[Tuple[str, str]]:
        return [(UploadPostProvider.key, UploadPostProvider.label)]

# ----------------------------
# Upload providers
# ----------------------------
class UploadProvider:
    """Resolve a local file path to a URL; plug in actual upload logic when available."""

    def ensure_video_url(self, path_or_url: str) -> str:
        if not path_or_url:
            raise ProviderError("Video path is empty.")
        if re.match(r"^https?://", str(path_or_url), re.IGNORECASE):
            return str(path_or_url)
        return str(Path(path_or_url).resolve())


class DryRunUploadProvider(UploadProvider):
    """During preview, allow local files to pass through as absolute paths."""
    def ensure_video_url(self, path_or_url: str) -> str:
        if re.match(r"^https?://", str(path_or_url), re.IGNORECASE):
            return path_or_url
        return str(Path(path_or_url).resolve())


# ----------------------------
# CSV parsing & inputs
# ----------------------------
class CsvMapping:
    REQUIRED_COLS = {"filename", "description"}
    OPTIONAL_COLS = {"name", "remark", "id", "video_url"}

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.rows: Dict[str, VideoRow] = {}

    def load(self) -> None:
        # Read a sample to help detection
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)

            # 1) Try Sniffer
            detected = ","
            try:
                detected = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            except Exception:
                pass

            def try_read(delim: str):
                f.seek(0)
                rdr = csv.DictReader(f, delimiter=delim)
                headers_raw = rdr.fieldnames or []
                return rdr, headers_raw

            rdr, headers_raw = try_read(detected)

            # 2) Fix "stuck" header like ['filename;description']
            if len(headers_raw) == 1 and headers_raw[0]:
                hdr0 = headers_raw[0]
                if ";" in hdr0:
                    rdr, headers_raw = try_read(";")
                elif "|" in hdr0:
                    rdr, headers_raw = try_read("|")
                elif "\t" in hdr0:
                    rdr, headers_raw = try_read("\t")

            # 3) fallback through common delimiters
            needed = {"filename", "description"}
            lowered = {h.strip().lower() for h in headers_raw}
            if not (needed <= lowered):
                for d in [";", ",", "\t", "|"]:
                    if d == detected:
                        continue
                    rdr2, hr2 = try_read(d)
                    if needed <= {h.strip().lower() for h in hr2}:
                        rdr, headers_raw = rdr2, hr2
                        break

            headers_set = {h.strip().lower() for h in headers_raw}
            missing = needed - headers_set
            if missing:
                raise ValueError(
                    f"CSV is missing required columns: {', '.join(sorted(missing))} "
                    f"(detected delimiter '{detected}', headers={list(headers_raw)})"
                )

            # 4) Read rows
            for rec in rdr:
                rec_lc = {(k or '').strip().lower(): (v or '') for k, v in rec.items()}
                fn = (rec_lc.get("filename") or "").strip()
                if not fn:
                    continue
                self.rows[Path(fn).name] = VideoRow(
                    filename=fn,
                    description=(rec_lc.get("description") or "").strip(),
                    name=(rec_lc.get("name") or None) or None,
                    remark=(rec_lc.get("remark") or None) or None,
                    user=(rec_lc.get("id") or None) or None,
                    video_url=(rec_lc.get("video_url") or None) or None,
                )

    def get_for(self, filename: str) -> Optional[VideoRow]:
        return self.rows.get(Path(filename).name)


# ----------------------------
# Scheduling logic
# ----------------------------
class Scheduler:
    def __init__(self, start_local: datetime, interval_minutes: int, tzinfo):
        self.start_local = start_local
        self.interval = timedelta(minutes=max(1, interval_minutes))
        self.tzinfo = tzinfo

    @staticmethod
    def parse_progression(text: str) -> Dict[int, int]:
        """Parse progression text into a {day_index: posts_per_day} dict. Days are 1‑based in the UI, store as 0‑based.
        Accepted formats:
          - "1:5, 2:10, 3:10"
          - JSON list: "[5,10,12]" (means day1=5, day2=10, day3=12)
        """
        text = (text or "").strip()
        if not text:
            return {}
        # JSON list form
        if text.startswith("[") and text.endswith("]"):
            try:
                arr = json.loads(text)
                out = {i: int(v) for i, v in enumerate(arr)}
                return out
            except Exception as e:
                raise ValueError(f"Invalid progression JSON: {e}")
        # day:count pairs form
        parts = re.split(r"[,\n]+", text)
        result: Dict[int, int] = {}
        for p in parts:
            if not p.strip():
                continue
            m = re.match(r"\s*(\d+)\s*[:=]\s*(\d+)\s*", p)
            if not m:
                raise ValueError(f"Bad progression token: '{p}'. Use '1:5, 2:10' or [5,10].")
            day1 = int(m.group(1))
            cnt = int(m.group(2))
            result[day1 - 1] = cnt
        return result

    def plan(self, items: List[VideoRow], defaults: Dict[str, str], uploader: UploadProvider) -> List[ScheduledItem]:
        """
        Возвращает список ScheduledItem. Правила:
          - Если у строки CSV есть `id`, публикуем только на этот телефон (не реплицируем).
          - Иначе:
              device_mode = replicate  -> каждое видео уходит на КАЖДЫЙ телефон из списка
              device_mode = round_robin -> распределяем по очереди
          - Если задана progression: per_day = кол-во уникальных видео на устройство за день.
            При replicate суммарно задач за день = per_day * len(phones) + строки с явным id.
          - fit_daily_window: для каждого дня интервал пересчитывается, чтобы уложиться в 24 часа
            (старт = то же локальное время, что у start_local; конец = +24h).
        """
        start_dt = self.start_local
        plan: List[ScheduledItem] = []

        device_mode = defaults.get("device_mode") or "round_robin"
        fit_daily = bool(defaults.get("fit_daily_window"))
        prog = self.parse_progression(defaults.get("progression", ""))

        user_list: List[str] = list(defaults.get("users", []) or [])
        default_user: Optional[str] = defaults.get("user") or None

        if not user_list and not default_user:
            if not any(row.user for row in items):
                raise ValueError("Upload user is required. Provide users list/range, a default user, or set id in CSV.")

        def day_start_for(index: int) -> datetime:
            base = start_dt + timedelta(days=index)
            return base.replace(second=0, microsecond=0)   # было: только microsecond


        def day_interval(per_day: int) -> timedelta:
            if not fit_daily or per_day <= 0:
                return self.interval
            window_sec = 24 * 60 * 60
            step_sec = max(int(window_sec // max(per_day, 1)), 60)  # минимум 1 минута
            return timedelta(seconds=step_sec)

        def schedule_one(row: VideoRow, when_local: datetime, seq_index: int) -> List[ScheduledItem]:
            """Schedule a single row for one or multiple upload users."""
            created: List[ScheduledItem] = []
            platforms_default = list(defaults.get("platforms") or [])
            if not platforms_default:
                platforms_default = [UploadPostProvider.SUPPORTED_DEFAULT_PLATFORM]

            if row.user:
                video_src = row.video_url or row.filename
                video_ref = uploader.ensure_video_url(video_src)
                description_raw = row.description or defaults.get("default_caption", "")
                description = clamp_text_for_api(description_raw, MAX_DESCRIPTION)

                name_raw = row.name or defaults.get("default_task_name")
                remark_raw = row.remark or defaults.get("default_remark")
                name = clamp_text_for_api(name_raw, MAX_NAME) if name_raw else None
                remark = clamp_text_for_api(remark_raw, MAX_REMARK) if remark_raw else None

                schedule_at = int(when_local.astimezone(tz.UTC).timestamp())
                payload = TaskPayload(
                    name=name,
                    remark=remark,
                    scheduleAt=schedule_at,
                    id=row.user,
                    description=description,
                    video=[video_ref],
                    platforms=list(platforms_default),
                )
                created.append(ScheduledItem(when_local, video_src, payload, row.filename))
                return created

            targets = []
            if device_mode == "replicate" and user_list:
                targets = user_list[:]
            else:
                if user_list:
                    targets = [user_list[seq_index % len(user_list)]]
                elif default_user:
                    targets = [default_user]
                else:
                    return created

            for tgt in targets:
                video_src = row.video_url or row.filename
                video_ref = uploader.ensure_video_url(video_src)
                description_raw = row.description or defaults.get("default_caption", "")
                description = clamp_text_for_api(description_raw, MAX_DESCRIPTION)

                name_raw = row.name or defaults.get("default_task_name")
                remark_raw = row.remark or defaults.get("default_remark")
                name = clamp_text_for_api(name_raw, MAX_NAME) if name_raw else None
                remark = clamp_text_for_api(remark_raw, MAX_REMARK) if remark_raw else None

                schedule_at = int(when_local.astimezone(tz.UTC).timestamp())
                payload = TaskPayload(
                    name=name,
                    remark=remark,
                    scheduleAt=schedule_at,
                    id=tgt,
                    description=description,
                    video=[video_ref],
                    platforms=list(platforms_default),
                )
                created.append(ScheduledItem(when_local, video_src, payload, row.filename))

            return created


        seq = 0  # инкремент для round-robin
        if prog:
            remaining = list(items)
            day_index = 0
            while remaining:
                per_day = int(prog.get(day_index, 0))
                if per_day <= 0:
                    break

                day_start = day_start_for(day_index)
                dd_interval = day_interval(per_day)

                # Берём per_day уникальных видео для ЭТОГО дня
                todays_rows = remaining[:per_day]
                remaining = remaining[per_day:]

                for i, row in enumerate(todays_rows):
                    when = day_start + i * dd_interval
                    created = schedule_one(row, when, seq)
                    plan.extend(created)
                    # Увеличиваем seq только на 1 уникальное видео (иначе round-robin скакнет слишком быстро)
                    seq += 1

                day_index += 1
        else:
            # Без прогрессии — линейно от старта по фиксированному интервалу
            for idx, row in enumerate(items):
                when = start_dt + idx * self.interval
                created = schedule_one(row, when, seq)
                plan.extend(created)
                seq += 1

        # отсортируем на всякий случай по времени
        plan.sort(key=lambda s: (s.local_dt, s.payload.id, s.source_filename))
        return plan


# ----------------------------
# Utilities
# ----------------------------
ROTATION_STATE_FILE = ".rotation_state.json"


class VideoRotationManager:
    """Persist and rotate video order to avoid replaying the same files."""

    def __init__(self, folder: Path, files: List[Path]):
        self.folder = folder
        self.files: List[Path] = list(files)
        self.order: List[str] = [p.name for p in files]
        self.offset: int = 0
        self.state_path = folder / ROTATION_STATE_FILE
        if self.files:
            self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        offset = int(data.get("offset", 0) or 0)
        stored_order = data.get("order")
        if isinstance(stored_order, list) and stored_order:
            if stored_order == self.order:
                self.offset = offset % len(self.files)
                return
            idx = offset % len(stored_order)
            next_name = stored_order[idx] if 0 <= idx < len(stored_order) else None
            if next_name and next_name in self.order:
                self.offset = self.order.index(next_name)
                return
        if self.files:
            self.offset = offset % len(self.files)

    def rotated_files(self) -> List[Path]:
        if not self.files or self.offset <= 0:
            return list(self.files)
        return self.files[self.offset:] + self.files[:self.offset]

    def advance(self, consumed: int) -> None:
        if not self.files:
            return
        consumed = consumed % len(self.files)
        if consumed <= 0:
            return
        self.offset = (self.offset + consumed) % len(self.files)
        payload = {"offset": self.offset, "order": self.order}
        try:
            self.state_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            # Persisting rotation is best-effort; ignore IO issues.
            pass


def discover_videos(folder: Path) -> List[Path]:
    vids: List[Path] = []
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in SUPPORTED_VIDEO_EXTS:
            vids.append(p)
    return vids


def bind_rows_to_files(file_list: List[Path], mapping: Optional[CsvMapping]) -> List[VideoRow]:
    rows: List[VideoRow] = []
    for p in file_list:
        row = mapping.get_for(p.name) if mapping else None
        if row is None:
            row = VideoRow(filename=p.name, description="")
        # Если в CSV нет готового URL — проставим абсолютный локальный путь для аплоада
        if not (row.video_url and re.match(r"^https?://", row.video_url, re.IGNORECASE)):
            row.video_url = str(p.resolve())
        rows.append(row)
    return rows



def parse_device_ids(text: str) -> List[str]:
    """Parse multiline/comma-separated IDs and numeric ranges like 1001-1010."""
    if not text:
        return []
    tokens = re.split(r"[\s,;]+", text.strip())
    result: List[str] = []
    for t in tokens:
        if not t:
            continue
        m = re.match(r"^(\d+)\s*[-:]{1,2}\s*(\d+)$", t)
        if m:
            a = int(m.group(1)); b = int(m.group(2))
            step = 1 if b >= a else -1
            w1, w2 = len(m.group(1)), len(m.group(2))
            width = w1 if w1 == w2 else 0
            for v in range(a, b + step, step):
                s = str(v).zfill(width) if width else str(v)
                result.append(s)
        else:
            result.append(t)
    seen = set()
    out: List[str] = []
    for i in result:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def parse_platforms(text: str) -> List[str]:
    if not text:
        return []
    tokens = [p.strip() for p in re.split(r"[\s,;]+", text.strip()) if p.strip()]
    seen = set()
    out: List[str] = []
    for token in tokens:
        lower = token.lower()
        if lower not in seen:
            seen.add(lower)
            out.append(lower)
    return out


def normalize_platforms(value) -> List[str]:
    if isinstance(value, list):
        tokens = [str(v).strip().lower() for v in value if str(v).strip()]
        seen = set()
        out: List[str] = []
        for token in tokens:
            if token not in seen:
                seen.add(token)
                out.append(token)
        return out
    if isinstance(value, str):
        return parse_platforms(value)
    return []





# ----------------------------
# Qt UI
# ----------------------------
class LogEdit(QtWidgets.QPlainTextEdit):
    def append_line(self, text: str):
        self.appendPlainText(text)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1180, 860)

        # State
        self.local_tz = tz.gettz()  # system tz
        self.uploader = UploadProvider()
        self.current_plan: List[ScheduledItem] = []
        self.rotation_manager: Optional[VideoRotationManager] = None

        # Widgets
        self.provider_combo = QtWidgets.QComboBox()
        for key, label in ProviderRegistry.options():
            self.provider_combo.addItem(label, userData=key)

        self.api_base_edit = QtWidgets.QLineEdit(UPLOAD_POST_DEFAULT_BASE)

        # Auth
        self.api_key_edit = QtWidgets.QLineEdit()
        self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.platforms_edit = QtWidgets.QLineEdit("instagram")

        # Device assignment mode
        self.replicate_check = QtWidgets.QCheckBox("Post each video on every device")
        self.replicate_check.setChecked(True)  # включим по умолчанию

        # Daily window fit
        self.fit_daily_window_check = QtWidgets.QCheckBox("Fit each day's posts into 24h window")
        self.fit_daily_window_check.setChecked(True)
        
        # Device IDs
        self.cloud_phone_edit = QtWidgets.QLineEdit()
        self.cloud_phone_list_edit = QtWidgets.QPlainTextEdit()
        self.cloud_phone_list_edit.setPlaceholderText(
            "One per line or comma; ranges like user_a, user_b-user_d"
        )

        # Defaults
        self.default_caption_edit = QtWidgets.QPlainTextEdit()
        self.default_task_name_edit = QtWidgets.QLineEdit()
        self.default_remark_edit = QtWidgets.QLineEdit()

        # Inputs
        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_btn = QtWidgets.QPushButton("Browse…")
        self.csv_edit = QtWidgets.QLineEdit()
        self.csv_btn = QtWidgets.QPushButton("CSV…")

        # Schedule controls
        self.start_dt = QtWidgets.QDateTimeEdit()
        self.start_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_dt.setCalendarPopup(True)
        now_local = datetime.now(self.local_tz)
        self.start_dt.setDateTime(now_local + timedelta(minutes=10))

        self.interval_spin = QtWidgets.QSpinBox()
        self.interval_spin.setRange(1, 24 * 60)
        self.interval_spin.setValue(15)

        self.progression_edit = QtWidgets.QPlainTextEdit()
        self.progression_edit.setPlaceholderText("Example: 1:5, 2:10, 3:10 or [5,10,10]")
        
        self.jitter_spin = QtWidgets.QSpinBox()
        self.jitter_spin.setRange(0, 3600)   # до часа «дрожания»
        self.jitter_spin.setValue(0)

        self.load_btn = QtWidgets.QPushButton("Preview plan")
        self.submit_btn = QtWidgets.QPushButton("Submit tasks (live)")
        self.export_btn = QtWidgets.QPushButton("Export plan CSV")
        self.dry_run_check = QtWidgets.QCheckBox("Dry run (no API calls)")
        self.dry_run_check.setChecked(True)

        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["#", "Local Time", "Filename", "User", "Caption (first 60)", "Task Name", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self.log = LogEdit()

        # Layout
        top = QtWidgets.QWidget()
        self.setCentralWidget(top)
        grid = QtWidgets.QGridLayout(top)

        r = 0
        grid.addWidget(QtWidgets.QLabel("Service"), r, 0)
        grid.addWidget(self.provider_combo, r, 1)
        grid.addWidget(QtWidgets.QLabel("API Base"), r, 2)
        grid.addWidget(self.api_base_edit, r, 3)
        grid.addWidget(QtWidgets.QLabel("Platforms (comma separated)"), r, 4)
        grid.addWidget(self.platforms_edit, r, 5)

        r += 1
        grid.addWidget(QtWidgets.QLabel("API Key"), r, 0)
        grid.addWidget(self.api_key_edit, r, 1, 1, 5)

        r += 1
        grid.addWidget(QtWidgets.QLabel("Default Upload User"), r, 0)
        grid.addWidget(self.cloud_phone_edit, r, 1)
        grid.addWidget(QtWidgets.QLabel("Upload Users (list/ranges)"), r, 2)
        grid.addWidget(self.cloud_phone_list_edit, r, 3, 1, 3)
        
        r += 1
        grid.addWidget(self.replicate_check, r, 0, 1, 3)
        grid.addWidget(self.fit_daily_window_check, r, 3, 1, 3)

        r += 1
        grid.addWidget(QtWidgets.QLabel("Default Task Name"), r, 0)
        grid.addWidget(self.default_task_name_edit, r, 1)
        grid.addWidget(QtWidgets.QLabel("Default Remark"), r, 2)
        grid.addWidget(self.default_remark_edit, r, 3, 1, 3)

        r += 1
        grid.addWidget(QtWidgets.QLabel("Default Caption"), r, 0)
        grid.addWidget(self.default_caption_edit, r, 1, 1, 5)

        r += 1
        grid.addWidget(QtWidgets.QLabel("Videos Folder"), r, 0)
        grid.addWidget(self.folder_edit, r, 1, 1, 4)
        grid.addWidget(self.folder_btn, r, 5)

        r += 1
        grid.addWidget(QtWidgets.QLabel("Captions CSV"), r, 0)
        grid.addWidget(self.csv_edit, r, 1, 1, 4)
        grid.addWidget(self.csv_btn, r, 5)

        r += 1
        grid.addWidget(QtWidgets.QLabel("Start Date/Time"), r, 0)
        grid.addWidget(self.start_dt, r, 1)
        grid.addWidget(QtWidgets.QLabel("Interval (min)"), r, 2)
        grid.addWidget(self.interval_spin, r, 3)
        grid.addWidget(QtWidgets.QLabel("Progression"), r, 4)
        grid.addWidget(self.progression_edit, r, 5)
        
        r += 1
        grid.addWidget(QtWidgets.QLabel("Jitter (± sec)"), r, 0)
        grid.addWidget(self.jitter_spin, r, 1)


        r += 1
        grid.addWidget(self.dry_run_check, r, 0)
        grid.addWidget(self.load_btn, r, 1)
        grid.addWidget(self.submit_btn, r, 2)
        grid.addWidget(self.export_btn, r, 3)

        r += 1
        grid.addWidget(self.table, r, 0, 1, 6)

        r += 1
        grid.addWidget(QtWidgets.QLabel("Log"), r, 0)
        grid.addWidget(self.log, r, 1, 1, 5)

        # Signals
        self.folder_btn.clicked.connect(self.pick_folder)
        self.csv_btn.clicked.connect(self.pick_csv)
        self.load_btn.clicked.connect(self.on_preview)
        self.submit_btn.clicked.connect(self.on_submit)
        self.export_btn.clicked.connect(self.on_export)

    # ---- UI handlers ----
    def pick_folder(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select videos folder")
        if d:
            self.folder_edit.setText(d)

    def pick_csv(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select captions CSV", filter="CSV files (*.csv)")
        if fn:
            self.csv_edit.setText(fn)

    def _load_inputs(self) -> Tuple[List[VideoRow], Dict[str, str]]:
        folder = Path(self.folder_edit.text().strip()) if self.folder_edit.text().strip() else None
        csv_path = Path(self.csv_edit.text().strip()) if self.csv_edit.text().strip() else None

        mapping = None
        if csv_path and csv_path.exists():
            mapping = CsvMapping(csv_path)
            mapping.load()
        else:
            self.log.append_line("CSV not provided or missing; rows will use default caption.")

        files: List[Path] = []
        self.rotation_manager = None
        if folder and folder.exists():
            source_files = discover_videos(folder)
            if not source_files:
                raise ValueError("No video files found in the selected folder.")
            manager = VideoRotationManager(folder, source_files)
            files = manager.rotated_files()
            self.rotation_manager = manager
        elif mapping:
            files = [Path(name) for name in mapping.rows.keys()]
        else:
            raise ValueError("Please select a videos folder or provide a CSV with video_url per row.")

        rows = bind_rows_to_files(files, mapping)

        default_caption_value = self.default_caption_edit.toPlainText().strip()

        # Filter out videos without captions when no default caption is provided.
        default_caption = default_caption_value
        filtered_rows: List[VideoRow] = []
        skipped_no_caption: List[str] = []
        for row in rows:
            row_caption = (row.description or "").strip()
            if not row_caption and not default_caption:
                skipped_no_caption.append(row.filename)
                continue
            filtered_rows.append(row)

        if skipped_no_caption:
            self.log.append_line(
                f"Skipped {len(skipped_no_caption)} video(s) without captions: "
                + ", ".join(skipped_no_caption[:5]) + ("..." if len(skipped_no_caption) > 5 else "")
            )

        rows = filtered_rows

        # Device IDs
        ids_text = self.cloud_phone_list_edit.toPlainText()
        multi_ids = parse_device_ids(ids_text)
        single_id = self.cloud_phone_edit.text().strip()
        # Allow both: concatenate with single at the end if provided
        users: List[str] = multi_ids.copy()
        if single_id:
            users.append(single_id)
        # De‑dupe while keeping order
        seen = set()
        users = [x for x in users if not (x in seen or seen.add(x))]

        defaults = {
            "user": single_id,
            "users": users,
            "platforms": normalize_platforms(self.platforms_edit.text()),
            "default_caption": default_caption_value,
            "default_task_name": self.default_task_name_edit.text().strip() or None,
            "default_remark": self.default_remark_edit.text().strip() or None,
            "progression": self.progression_edit.toPlainText().strip(),
            "device_mode": "replicate" if self.replicate_check.isChecked() else "round_robin",
            "fit_daily_window": self.fit_daily_window_check.isChecked(),
            "jitter_sec": int(self.jitter_spin.value()),
        }
        if not defaults["platforms"]:
            defaults["platforms"] = [UploadPostProvider.SUPPORTED_DEFAULT_PLATFORM]
        return rows, defaults

    def _build_plan(self) -> List[ScheduledItem]:
        rows, defaults = self._load_inputs()
        start_dt_local = self.start_dt.dateTime().toPython()
        start_dt_local = start_dt_local.replace(tzinfo=self.local_tz)
        scheduler = Scheduler(
            start_local=start_dt_local,
            interval_minutes=int(self.interval_spin.value()),
            tzinfo=self.local_tz
        )
        plan = scheduler.plan(rows, defaults, uploader=self.uploader)
        jitter_sec = int(defaults.get("jitter_sec") or 0)
        if jitter_sec > 0:
            rnd = random.Random()  # можно задать seed, если нужен детерминизм
            for item in plan:
                offset = rnd.randint(-jitter_sec, jitter_sec)
                if offset != 0:
                    item.local_dt = item.local_dt + timedelta(seconds=offset)
                    item.payload.scheduleAt = int(item.local_dt.astimezone(tz.UTC).timestamp())
            # чтобы таблица шла по времени после сдвигов
            plan.sort(key=lambda s: (s.local_dt, s.payload.id, s.source_filename))
        return plan

    def on_preview(self):
        try:
            # use dry-run uploader to avoid requiring URLs during planning
            original = self.uploader
            self.uploader = DryRunUploadProvider()
            self.current_plan = self._build_plan()
            self.render_plan()
            self.log.append_line(
                f"Planned {len(self.current_plan)} tasks. "
                f"(Dry run is {'ON' if self.dry_run_check.isChecked() else 'OFF'})"
            )
        except Exception as e:
            self.log.append_line(f"[ERROR] {e}")
            traceback.print_exc()
        finally:
            # restore real uploader
            self.uploader = original

    def render_plan(self):
        self.table.setRowCount(0)
        for i, item in enumerate(self.current_plan, start=1):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(i)))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(item.local_dt.strftime("%Y-%m-%d %H:%M")))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(item.source_filename))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(item.payload.id))
            cap = item.payload.description or ""
            if len(cap) > 60:
                cap = cap[:57] + "…"
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(cap))
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(item.payload.name or ""))
            self.table.setItem(r, 6, QtWidgets.QTableWidgetItem("Planned"))

    def on_submit(self):
        # (1) Build plan if missing        
        if not self.current_plan:
            try:
                self.current_plan = self._build_plan()
                self.render_plan()
            except Exception as e:
                self.log.append_line(f"[ERROR] {e}")
                return

        # (2) Provider and headers
        provider_key = self.provider_combo.currentData() or 'upload_post'
        api_base = self.api_base_edit.text().strip() or UPLOAD_POST_DEFAULT_BASE
        api_key = self.api_key_edit.text().strip() or None
        masked_key = ''
        if api_key:
            masked_key = api_key[:4] + '***' + api_key[-4:] if len(api_key) > 8 else api_key
        self.log.append_line(
            f'Using API base={api_base} API key={masked_key}'
        )

        provider = ProviderRegistry.create(
            provider_key,
            api_base=api_base,
            api_key=api_key,
        )

        # (3) Mode
        do_live = not self.dry_run_check.isChecked()
        posted = 0
        rotation_manager = self.rotation_manager if do_live else None
        successful_sources: List[str] = []
        success_seen: Set[str] = set()

        for idx, item in enumerate(self.current_plan):
            vid = item.payload.video[0] if item.payload.video else item.video_path_or_url
            if do_live:
                try:
                    status, text = provider.submit(item)
                    info = parse_upload_post_response(text)
                    ok_http = status < 400
                    success_flag = bool(info['success']) if info['success'] is not None else ok_http
                    request_id = info.get('request_id')
                    message = info.get('message')
                    platforms_note = ','.join(item.payload.platforms) if item.payload.platforms else '-'
                    if ok_http and success_flag:
                        self.log.append_line(
                            f"[{idx+1}] OK {status} request_id={request_id or '-'} | user={item.payload.id} | platforms={platforms_note} | msg={message or 'success'}"
                        )
                        if rotation_manager and item.source_filename not in success_seen:
                            success_seen.add(item.source_filename)
                            successful_sources.append(item.source_filename)
                        if self.table.item(idx, 6):
                            self.table.item(idx, 6).setText('Submitted')
                        posted += 1
                    else:
                        self.log.append_line(
                            f"[{idx+1}] FAIL HTTP {status} success={info.get('success')} request_id={request_id or '-'} | user={item.payload.id} | platforms={platforms_note} | msg={message} body={text[:400]}"
                        )
                        if self.table.item(idx, 6):
                            self.table.item(idx, 6).setText(f'HTTP {status}')
                    append_trace_log({
                        'ts': datetime.utcnow().isoformat(),
                        'context': 'gui.submit',
                        'index': idx + 1,
                        'user': item.payload.id,
                        'platforms': item.payload.platforms,
                        'scheduleAt': item.payload.scheduleAt,
                        'source': item.source_filename,
                        'status': status,
                        'http_ok': ok_http,
                        'api_success': info.get('success'),
                        'request_id': request_id,
                        'message': message,
                        'results': info.get('results'),
                        'usage': info.get('usage'),
                        'response': text,
                        'payload': dataclasses.asdict(item.payload),
                        'description_len': len(item.payload.description or ''),
                    })
                except Exception as e:
                    self.log.append_line(f"[{idx+1}] ERROR: {e}")
                    if self.table.item(idx, 6):
                        self.table.item(idx, 6).setText('Error')
            else:
                # Dry-run
                try:
                    utc_str = datetime.utcfromtimestamp(item.payload.scheduleAt).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    utc_str = "n/a"
                platforms_note = ','.join(item.payload.platforms) if item.payload.platforms else '-'
                self.log.append_line(
                    f"[DRY] Would submit {idx+1}: {item.source_filename} | user={item.payload.id} | platforms={platforms_note} "
                    f"at {item.local_dt.strftime('%Y-%m-%d %H:%M')} (UTC={utc_str}) | video={vid}"
                )
                if self.table.item(idx, 6):
                    self.table.item(idx, 6).setText("Planned")

        if do_live and rotation_manager and successful_sources:
            rotation_manager.advance(len(successful_sources))

        if do_live:
            self.log.append_line(f"Done. Submitted {posted}/{len(self.current_plan)} tasks.")
        else:
            self.log.append_line("Dry run complete. Toggle OFF to submit for real.")

    def on_export(self):
        if not self.current_plan:
            try:
                self.current_plan = self._build_plan()
            except Exception as e:
                self.log.append_line(f"[ERROR] {e}")
                return
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save plan CSV", filter="CSV files (*.csv)")
        if not fn:
            return
        path = Path(fn)
        with path.open("w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["idx", "local_time", "utc_epoch", "filename", "user", "description", "task_name", "remark", "video_url"])
            for i, item in enumerate(self.current_plan, start=1):
                wr.writerow([
                    i,
                    item.local_dt.isoformat(),
                    item.payload.scheduleAt,
                    item.source_filename,
                    item.payload.id,
                    item.payload.description,
                    item.payload.name or "",
                    item.payload.remark or "",
                    item.payload.video[0],
                ])
        self.log.append_line(f"Exported plan → {path}")
        
# --- Headless API для orchestrator.py ---
def do_post(payload: dict) -> dict:
    """Headless posting entry point used by orchestrator/CLI."""
    provider_key = payload.get("provider", UploadPostProvider.key)
    api_base = payload.get("api_base", UPLOAD_POST_DEFAULT_BASE)
    api_key = payload.get("api_key") or payload.get("token")
    if not api_key:
        raise ValueError("Payload must include 'api_key' (Upload-Post API key).")

    provider = ProviderRegistry.create(
        provider_key,
        api_base=api_base,
        api_key=api_key,
    )

    platforms = normalize_platforms(payload.get("platforms"))
    if not platforms:
        platforms = [UploadPostProvider.SUPPORTED_DEFAULT_PLATFORM]

    # Legacy fields: device_ids -> users
    users: List[str] = []
    raw_users = payload.get("users")
    if isinstance(raw_users, list):
        users = [str(u).strip() for u in raw_users if str(u).strip()]
    legacy_ids = payload.get("device_ids")
    if legacy_ids:
        users.extend(parse_device_ids(str(legacy_ids)))
    default_user = (payload.get("user") or "").strip() or None
    if default_user:
        users.append(default_user)
    # De-duplicate while keeping order
    seen_users: set[str] = set()
    users = [u for u in users if not (u in seen_users or seen_users.add(u))]
    if not users and not default_user:
        raise ValueError("Upload user is required. Provide 'user', 'users', or device_ids in payload.")

    # Optional title/description overrides per platform from payload
    title_overrides = {k[:-6]: v for k, v in payload.items() if k.endswith('_title') and isinstance(v, str)}
    description_overrides = {k[:-12]: v for k, v in payload.items() if k.endswith('_description') and isinstance(v, str)}

    # Single direct upload (without folder/csv)
    direct_video = payload.get("video") or payload.get("video_url") or payload.get("filename")
    if direct_video:
        if not default_user:
            raise ValueError("Single upload requires 'user' in payload.")
        uploader = UploadProvider()
        video_ref = uploader.ensure_video_url(str(direct_video))
        schedule_at = payload.get("schedule_at")
        if schedule_at is None:
            start_str = payload.get("start")
            tzinfo = tz.gettz(payload.get("tz")) or tz.gettz()
            now_local = datetime.now(tzinfo)
            if start_str and re.match(r"^\d{1,2}:\d{2}$", start_str):
                hh, mm = map(int, start_str.split(":"))
                dt_local = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if dt_local <= now_local:
                    dt_local += timedelta(days=1)
            elif start_str:
                dt_local = datetime.strptime(start_str, "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
            else:
                dt_local = now_local
            schedule_at = int(dt_local.astimezone(timezone.utc).timestamp())
        scheduled = ScheduledItem(
            datetime.utcnow(),
            str(direct_video),
            TaskPayload(
                name=payload.get("name"),
                remark=payload.get("remark"),
                scheduleAt=int(schedule_at),
                id=default_user,
                description=payload.get("description", ""),
                video=[video_ref],
                platforms=list(platforms),
                title_overrides=title_overrides,
                description_overrides=description_overrides,
            ),
            Path(video_ref).name,
        )
        status, text = provider.submit(scheduled)
        info = parse_upload_post_response(text)
        ok_http = status < 400
        result = {
            "status": status,
            "success": info.get("success") if info.get("success") is not None else ok_http,
            "message": info.get("message"),
            "request_id": info.get("request_id"),
            "results": info.get("results"),
            "usage": info.get("usage"),
            "response": text,
        }
        append_trace_log({
            "ts": datetime.utcnow().isoformat(),
            "context": "headless.single",
            "user": scheduled.payload.id,
            "platforms": scheduled.payload.platforms,
            "scheduleAt": scheduled.payload.scheduleAt,
            "source": scheduled.source_filename,
            "status": status,
            "http_ok": ok_http,
            "api_success": info.get("success"),
            "request_id": info.get("request_id"),
            "message": info.get("message"),
            "results": info.get("results"),
            "usage": info.get("usage"),
            "response": text,
            "payload": dataclasses.asdict(scheduled.payload),
        })
        return result

    # Batch upload (folder/csv)
    uploader = UploadProvider()
    folder = Path(payload.get("folder") or "")
    csv_path = Path(payload.get("csv") or "")
    mapping = None
    if csv_path and csv_path.exists():
        mapping = CsvMapping(csv_path)
        mapping.load()

    files: List[Path] = []
    rotation_manager: Optional[VideoRotationManager] = None
    if folder and folder.exists():
        source_files = discover_videos(folder)
        if not source_files:
            raise ValueError("No videos found to post.")
        rotation_manager = VideoRotationManager(folder, source_files)
        files = rotation_manager.rotated_files()
    elif mapping:
        files = [Path(name) for name in mapping.rows.keys()]
    if not files:
        raise ValueError("No videos found to post.")

    rows = bind_rows_to_files(files, mapping)

    default_caption_value = (payload.get("default_caption") or "").strip()
    filtered_rows: List[VideoRow] = []
    skipped_no_caption: List[str] = []
    for row in rows:
        row_caption = (row.description or "").strip()
        if not row_caption and not default_caption_value:
            skipped_no_caption.append(row.filename)
            continue
        filtered_rows.append(row)
    rows = filtered_rows

    tzinfo = tz.gettz(payload.get("tz")) or tz.gettz()
    now_local = datetime.now(tzinfo)
    start_str = payload.get("start")
    if start_str and re.match(r"^\d{1,2}:\d{2}$", start_str):
        hh, mm = map(int, start_str.split(":"))
        start_local = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if start_local <= now_local:
            start_local = start_local + timedelta(days=1)
    elif start_str:
        start_local = datetime.strptime(start_str, "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
    else:
        start_local = now_local

    scheduler = Scheduler(
        start_local=start_local,
        interval_minutes=int(payload.get("interval", 15)),
        tzinfo=tzinfo,
    )
    defaults = {
        "user": default_user,
        "users": users,
        "platforms": platforms,
        "default_caption": default_caption_value,
        "default_task_name": payload.get("name"),
        "default_remark": payload.get("remark"),
        "progression": payload.get("progression", ""),
        "device_mode": "replicate" if payload.get("replicate", True) else "round_robin",
        "fit_daily_window": bool(payload.get("fit_daily_window", True)),
        "jitter_sec": int(payload.get("jitter", 0)),
    }
    if not defaults["platforms"]:
        defaults["platforms"] = [UploadPostProvider.SUPPORTED_DEFAULT_PLATFORM]

    plan = scheduler.plan(rows, defaults, uploader=uploader)

    live = bool(payload.get("live", False))
    submitted = 0
    submissions = []
    successful_sources: List[str] = []
    success_seen: Set[str] = set()

    for idx, item in enumerate(plan, start=1):
        if live:
            status, text = provider.submit(item)
            info = parse_upload_post_response(text)
            ok_http = status < 400
            success_flag = bool(info['success']) if info.get('success') is not None else ok_http
            request_id = info.get('request_id')
            message = info.get('message')
            if ok_http and success_flag:
                submitted += 1
                if rotation_manager and item.source_filename not in success_seen:
                    success_seen.add(item.source_filename)
                    successful_sources.append(item.source_filename)
            record = {
                "index": idx,
                "status": status,
                "success": success_flag,
                "message": message,
                "request_id": request_id,
                "results": info.get('results'),
                "usage": info.get('usage'),
                "user": item.payload.id,
                "platforms": item.payload.platforms,
                "scheduleAt": item.payload.scheduleAt,
                "source": item.source_filename,
                "response": text,
            }
            submissions.append(record)
            append_trace_log({
                "ts": datetime.utcnow().isoformat(),
                "context": "headless.batch",
                **record,
                "http_ok": ok_http,
                "api_success": info.get('success'),
                "payload": dataclasses.asdict(item.payload),
            })
        else:
            submissions.append({
                "index": idx,
                "status": "DRY",
                "user": item.payload.id,
                "platforms": item.payload.platforms,
                "scheduleAt": item.payload.scheduleAt,
                "source": item.source_filename,
            })

    if live and rotation_manager and successful_sources:
        rotation_manager.advance(len(successful_sources))

    for fname in skipped_no_caption:
        submissions.append({
            "status": "SKIPPED_NO_CAPTION",
            "message": "Missing caption and no default caption provided",
            "source": fname,
        })

    return {
        "status": 200,
        "response": "ok",
        "planned": len(plan),
        "submitted": submitted,
        "live": live,
        "submissions": submissions,
    }

def main():
    app = QtWidgets.QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()





