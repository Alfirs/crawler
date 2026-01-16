# app/services/neuro_client.py
import os
import requests
from typing import Tuple

def get_neuroapi_creds() -> Tuple[str, str]:
    """Читает актуальные значения ключа и базового URL."""
    key = (os.getenv("NEUROAPI_API_KEY") or "").strip()
    base = (os.getenv("NEUROAPI_BASE_URL") or "https://neuroapi.host/v1").strip()
    return key, base

def neuroapi_enabled() -> bool:
    """Проверяет, настроен ли NeuroAPI для использования."""
    key, base = get_neuroapi_creds()
    return bool(key) and base.startswith("http")

def neuroapi_request(endpoint: str, payload: dict, files=None, timeout: int = 60):
    """
    Выполняет запрос к NeuroAPI с актуальными credentials.
    """
    key, base = get_neuroapi_creds()
    if not key:
        # Диагностика для отладки
        all_keys = list(os.environ.keys())
        neuro_keys = [k for k in all_keys if 'NEURO' in k]
        print(f"[NeuroAPI] DIAG: getenv('NEUROAPI_API_KEY') -> {repr(os.getenv('NEUROAPI_API_KEY'))}")
        print(f"[NeuroAPI] DIAG: neuro env keys -> {neuro_keys}")
        raise RuntimeError("NEUROAPI_API_KEY is not set")
    
    url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {"Authorization": f"Bearer {key}"}
    
    if files:
        headers.pop("Content-Type", None)  # requests установит автоматически для multipart
        resp = requests.post(url, headers=headers, data=payload, files=files, timeout=timeout)
    else:
        headers["Content-Type"] = "application/json"
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    
    if not resp.ok:
        raise RuntimeError(f"[NeuroAPI] HTTP {resp.status_code}: {resp.text[:200]}")
    
    return resp

def get_neuro_client():
    """
    Для обратной совместимости - создает OpenAI клиент с актуальными credentials.
    """
    from openai import OpenAI
    key, base = get_neuroapi_creds()
    if not key:
        raise RuntimeError("NEUROAPI_API_KEY is not set")
    return OpenAI(base_url=base, api_key=key)

