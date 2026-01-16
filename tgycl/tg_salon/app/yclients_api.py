from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional

import requests

logger = logging.getLogger(__name__)

SERVICES_PATH = "/services/{company_id}"
STAFF_PATH = "/staff/{company_id}"
FREE_SLOTS_PATH = "/book_times/{company_id}/{staff_id}"
FREE_SLOTS_FALLBACK_PATH = "/book_times/{company_id}"
CREATE_RECORD_PATH = "/records/{company_id}"

ACCEPT_HEADER = "application/vnd.yclients.v2+json"


class YclientsAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"YCLIENTS API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


@dataclass
class YclientsAPI:
    base_url: str
    partner_token: str
    user_token: str
    strict_v2: bool = True
    services_cache_ttl: int = 300
    session: requests.Session = field(default_factory=requests.Session)

    _services_cache: dict[int, tuple[float, list[dict]]] = field(default_factory=dict, init=False)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": ACCEPT_HEADER,
            "Authorization": f"Bearer {self.partner_token}, User {self.user_token}",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}" if not path.startswith("http") else path

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = self._url(path)
        headers = kwargs.pop("headers", {})
        merged_headers = {**self._headers(), **headers}
        response = self.session.request(method=method, url=url, headers=merged_headers, timeout=30, **kwargs)
        if not response.ok:
            try:
                payload = response.json()
            except ValueError:
                raise YclientsAPIError(response.status_code, response.text)
            message = (
                payload.get("message")
                or payload.get("error")
                or payload.get("detail")
                or payload.get("title")
                or response.text
            )
            raise YclientsAPIError(response.status_code, message)
        try:
            payload = response.json()
        except ValueError as exc:
            raise YclientsAPIError(response.status_code, "Invalid JSON in response") from exc
        return payload

    def _extract_data(self, payload: dict) -> Any:
        if self.strict_v2 and "data" in payload:
            return payload["data"]
        if not self.strict_v2 and "data" in payload and isinstance(payload["data"], list):
            return payload["data"]
        return payload

    def get_services(self, company_id: int, use_cache: bool = True) -> List[dict]:
        cached = self._services_cache.get(company_id)
        now_ts = datetime.now(timezone.utc).timestamp()
        if use_cache and cached and cached[0] > now_ts:
            return cached[1]
        payload = self._request("GET", SERVICES_PATH.format(company_id=company_id))
        services = list(self._extract_data(payload))
        if use_cache:
            self._services_cache[company_id] = (now_ts + self.services_cache_ttl, services)
        return services

    def get_staff(
        self,
        company_id: int,
        service_id: Optional[int] = None,
        date_iso: Optional[str] = None,
    ) -> List[dict]:
        params: dict[str, Any] = {}
        if service_id:
            params["service_id"] = service_id
        if date_iso:
            params["date"] = date_iso
        payload = self._request("GET", STAFF_PATH.format(company_id=company_id), params=params)
        return list(self._extract_data(payload))

    def get_free_slots(
        self,
        company_id: int,
        staff_id: int,
        service_id: int,
        date_iso: str,
    ) -> List[str]:
        params = {"service_id": service_id, "date": date_iso, "staff_id": staff_id}
        logger.debug(
            "Requesting book_times company=%s staff=%s service=%s date=%s",
            company_id,
            staff_id,
            service_id,
            date_iso,
        )
        try:
            payload = self._request(
                "GET",
                FREE_SLOTS_PATH.format(company_id=company_id, staff_id=staff_id),
                params=params,
            )
        except YclientsAPIError as exc:
            if exc.status_code == 404:
                logger.info(
                    "book_times/%s/%s not found, trying fallback path",
                    company_id,
                    staff_id,
                )
                try:
                    payload = self._request(
                        "GET",
                        FREE_SLOTS_FALLBACK_PATH.format(company_id=company_id),
                        params=params,
                    )
                except YclientsAPIError as fallback_exc:
                    if fallback_exc.status_code == 404:
                        logger.warning(
                            "YCLIENTS book_times returned 404 for both staff-specific and fallback "
                            "paths (company=%s, staff=%s, service=%s, date=%s)",
                            company_id,
                            staff_id,
                            service_id,
                            date_iso,
                        )
                        return []
                    raise
            else:
                raise
        data = self._extract_data(payload)
        if isinstance(data, dict) and "book_times" in data:
            slots_data = data["book_times"]
        else:
            slots_data = data
        slots: List[str] = []
        for item in slots_data:
            if isinstance(item, dict):
                start = item.get("time") or item.get("start_time") or item.get("datetime")
                if start:
                    slots.append(str(start)[11:16])
            else:
                slots.append(str(item))
        if not slots:
            logger.warning(
                "YCLIENTS returned zero slots for company=%s staff=%s service=%s date=%s. Raw response=%s",
                company_id,
                staff_id,
                service_id,
                date_iso,
                slots_data,
            )
        else:
            logger.info(
                "Loaded %s slots for company=%s staff=%s service=%s date=%s",
                len(slots),
                company_id,
                staff_id,
                service_id,
                date_iso,
            )
        return sorted({slot for slot in slots})

    def create_record(
        self,
        company_id: int,
        service_id: int,
        staff_id: int,
        start_iso: str,
        client_name: str,
        client_phone: str,
        comment: str = "",
    ) -> dict:
        payload = {
            "datetime": start_iso,
            "comment": comment,
            "services": [
                {
                    "id": service_id,
                    "staff_id": staff_id,
                }
            ],
            "staff_id": staff_id,
            "client": {
                "name": client_name,
                "phone": client_phone,
            },
            "phone": client_phone,
            "name": client_name,
        }
        response = self._request(
            "POST",
            CREATE_RECORD_PATH.format(company_id=company_id),
            json=payload,
        )
        return self._extract_data(response)
