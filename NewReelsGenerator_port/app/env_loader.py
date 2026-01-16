# app/env_loader.py
from __future__ import annotations
import os
import re
from typing import Tuple, Optional

_VALID_KEY_RE = re.compile(r"^[A-Z0-9_]+$", re.ASCII)

def _sanitize_bytes_to_text(path: str) -> str:
    # Читаем как байты, убираем NUL, декодируем с BOM-стрипом
    with open(path, "rb") as f:
        raw = f.read()
    raw = raw.replace(b"\x00", b"")  # критично: убираем NUL заранее
    # utf-8-sig удалит BOM, errors="ignore" проглотит битые байты
    return raw.decode("utf-8-sig", errors="ignore")

def _unquote(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and ((val[0] == val[-1] == '"') or (val[0] == val[-1] == "'")):
        val = val[1:-1]
    # Поддержка \n \t и т.п.
    val = val.encode("utf-8", "backslashreplace").decode("unicode_escape", "ignore")
    return val

def _strip_inline_comment(val: str) -> str:
    """
    Если значение не в кавычках — обрезаем инлайн-комментарий после пробела-решётки.
    В кавычках — оставляем как есть.
    """
    s = val.lstrip()
    if s.startswith(("'", '"')):
        # Значение в кавычках — комментарий может быть внутри, не трогаем.
        return val
    # Вне кавычек: режем по ' #'
    hash_pos = val.find(" #")
    if hash_pos != -1:
        return val[:hash_pos].rstrip()
    return val

def _parse_line(line: str) -> Optional[Tuple[str, str]]:
    # Игнор пустых/комментариев
    s = line.strip()
    if not s or s.startswith("#"):
        return None

    # Поддержка "export KEY=VAL"
    if s.lower().startswith("export "):
        s = s[7:].lstrip()

    # Должен быть "KEY=VAL"
    if "=" not in s:
        return None

    key, val = s.split("=", 1)
    key = key.strip()
    if not key or not _VALID_KEY_RE.match(key):
        # некорректный ключ — пропускаем
        return None

    val = _strip_inline_comment(val).strip()
    val = _unquote(val)

    # Удаляем NUL на всякий случай
    val = val.replace("\x00", "")

    return key, val

def _safe_setenv(key: str, val: str) -> bool:
    try:
        # os.environ сам бросает ValueError на NUL — мы уже очистили,
        # но ещё раз проверим, чтобы гарантированно не упасть.
        if "\x00" in key or "\x00" in val:
            return False
        os.environ[key] = val
        return True
    except Exception:
        return False

def load_env(env_path: str | None = None) -> dict:
    """
    Надёжная загрузка переменных из .env без падений.
    
    Args:
        env_path: Путь к .env файлу. Если None, ищет .env в текущей директории.
        
    Returns:
        Словарь загруженных переменных
    """
    path = env_path or ".env"
    
    # Делаем путь абсолютным для лучшей отладки
    abs_path = os.path.abspath(path)
    
    if not os.path.exists(abs_path):
        print(f"[ENV_LOADER] WARNING: .env not found at {abs_path}")
        return {}

    text = _sanitize_bytes_to_text(abs_path)
    applied, skipped = 0, 0
    loaded_vars = {}

    for raw_line in text.splitlines():
        # Приводим к UNIX-стилю и убираем непечатные
        line = raw_line.replace("\r", "").strip()
        if not line:
            continue

        parsed = _parse_line(line)
        if not parsed:
            skipped += 1
            continue

        key, val = parsed
        if _safe_setenv(key, val):
            applied += 1
            loaded_vars[key] = val
        else:
            skipped += 1

    print(f"[ENV_LOADER] applied={applied} skipped={skipped} path={abs_path}")
    return loaded_vars