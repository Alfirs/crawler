from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from .config import APISettings


class WildberriesAPI:
    """Client for interacting with Wildberries supplier endpoints."""

    def __init__(self, settings: APISettings, *, client: Optional[httpx.Client] = None) -> None:
        self.settings = settings
        headers = {"Authorization": settings.api_key or ""}
        self._client = client or httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout,
            headers=headers,
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response = self._client.request(method, endpoint, params=params, json=json)
        response.raise_for_status()
        return response.json()

    def get_orders(self, date_from: str, status: str = "all") -> Dict[str, Any]:
        """Fetch orders for analytics dashboards."""
        params = {"dateFrom": date_from, "status": status}
        return self._request("GET", "/api/v2/orders", params=params)

    def get_supplies(self) -> Dict[str, Any]:
        """Retrieve supply info for warehouse flow tracking."""
        return self._request("GET", "/api/v2/supplies")

    def get_stocks(self, warehouse_id: Optional[int] = None) -> Dict[str, Any]:
        params = {}
        if warehouse_id:
            params["warehouseId"] = warehouse_id
        return self._request("GET", "/api/v2/stocks", params=params)

    def get_detail_report(self, date_from: str, date_to: str) -> Dict[str, Any]:
        """Detailed finance report for neural analytics."""
        params = {"dateFrom": date_from, "dateTo": date_to}
        return self._request("GET", "/api/v1/supplier/reportDetailByPeriod", params=params)
