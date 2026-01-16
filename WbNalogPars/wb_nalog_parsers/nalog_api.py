from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

import httpx

from .config import APISettings


class NalogAPI:
    """Thin wrapper around the public FNS (налоговая) API endpoints."""

    def __init__(self, settings: APISettings, *, client: Optional[httpx.Client] = None) -> None:
        self.settings = settings
        self._client = client or httpx.Client(base_url=settings.base_url, timeout=settings.timeout)

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = {}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"

        response = self._client.request(method, endpoint, params=params, json=json, headers=headers)
        response.raise_for_status()
        return response.json()

    def search_company(self, inn: str, kpp: Optional[str] = None) -> Dict[str, Any]:
        """Request company details by ИНН/КПП."""
        params = {"inn": inn}
        if kpp:
            params["kpp"] = kpp
        return self._request("GET", "/entities/companies/search", params=params)

    def fetch_tax_debt(self, inn: str) -> Dict[str, Any]:
        """Fetch information about existing tax debts."""
        return self._request("GET", "/entities/companies/debt", params={"inn": inn})

    def fetch_licenses(self, inn: str) -> Dict[str, Any]:
        """Retrieve licences or permits the company currently has."""
        return self._request("GET", "/entities/companies/licenses", params={"inn": inn})

    def fetch_statements(
        self,
        inn: str,
        *,
        date_from: date,
        date_to: date,
    ) -> Dict[str, Any]:
        """Download book-keeping statements for further analytics."""
        payload = {"inn": inn, "date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
        return self._request("POST", "/documents/statements", json=payload)
