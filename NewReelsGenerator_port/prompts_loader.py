from __future__ import annotations

from pathlib import Path
from typing import Optional, Set, Dict, Any

import yaml


def _read_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid prompt file format: expected mapping at root in {path}")
    return data


def _load_account_merged(account: str, base_dir: Optional[Path] = None, _seen: Optional[Set[str]] = None) -> Dict[str, Any]:
    """Load account YAML with optional inheritance via key 'extends'.

    If config/prompts/<account>.yaml contains 'extends: <parent>', the parent's
    mapping is loaded first, then overridden by child's keys. Single-level string
    extends supported recursively; cycles are detected.
    """
    if _seen is None:
        _seen = set()
    if account in _seen:
        raise ValueError(f"Cyclic 'extends' detected in prompts for account '{account}'")
    _seen.add(account)

    root = base_dir if base_dir is not None else Path(__file__).resolve().parent
    cfg_path = root / "config" / "prompts" / f"{account}.yaml"
    if not cfg_path.exists():
        raise ValueError(f"Prompt config not found for account '{account}': {cfg_path}")

    data = _read_yaml(cfg_path)
    parent = data.get("extends")
    if isinstance(parent, str) and parent.strip():
        base = _load_account_merged(parent.strip(), base_dir=base_dir, _seen=_seen)
        # Child overrides parent (shallow merge)
        merged = dict(base)
        merged.update({k: v for k, v in data.items() if k != "extends"})
        return merged
    return data


def load_prompt_for_account(account: str, mode: str, base_dir: Optional[Path] = None) -> str:
    """
    Load an account-specific prompt for the given mode from config/prompts/<account>.yaml.

    Required YAML keys inside the account file:
      - description         (for mode == "titles")
      - title_description   (for mode != "titles", e.g., "topics")

    Raises ValueError with a clear message if something is missing.
    """
    if not account or not isinstance(account, str):
        raise ValueError("Account key must be a non-empty string.")

    try:
        data = _load_account_merged(account, base_dir=base_dir)
    except Exception as e:
        raise ValueError(f"Failed to load prompt config for account '{account}': {e}")

    key = "description" if mode == "titles" else "title_description"
    prompt = data.get(key)
    if not isinstance(prompt, str) or not prompt.strip():
        root = base_dir if base_dir is not None else Path(__file__).resolve().parent
        cfg_path = root / 'config' / 'prompts' / f"{account}.yaml"
        raise ValueError(
            f"Prompt for account '{account}' and mode '{mode}' is missing or empty. "
            f"Expected key '{key}' in {cfg_path}"
        )
    return prompt


def load_footer_for_account(account: str, base_dir: Optional[Path] = None) -> str:
    """Load optional CTA/footer text for the account.

    Looks for keys 'footer' or 'cta' in config/prompts/<account>.yaml.
    Returns empty string if not provided or file is missing.
    """
    try:
        data = _load_account_merged(account, base_dir=base_dir)
        footer = data.get("footer") or data.get("cta") or ""
        return footer if isinstance(footer, str) else ""
    except Exception:
        return ""

def load_title_description_separator(account: str, base_dir: Optional[Path] = None) -> str:
    """Return the delimiter used to split title and description in model output."""
    default = "|||"
    try:
        data = _load_account_merged(account, base_dir=base_dir)
    except Exception:
        return default
    sep = data.get("title_description_separator") or data.get("separator")
    if isinstance(sep, str) and sep.strip():
        return sep
    return default

