from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import aiohttp
from typing import Dict, Optional

logger = logging.getLogger(__name__)

@dataclass
class CurrencyRates:
    usd: float
    eur: float
    cny: float
    updated_at: datetime
    
    @property
    def usd_with_margin(self) -> float:
        return self.usd * 1.02
        
    @property
    def cny_with_margin(self) -> float:
        return self.cny * 1.02
        
    @property
    def eur_with_margin(self) -> float:
        return self.eur * 1.02

class RateProvider:
    _instance: Optional[RateProvider] = None
    _cache: Optional[CurrencyRates] = None
    _last_update: Optional[datetime] = None
    
    def __init__(self, cbr_url: str = "https://www.cbr-xml-daily.ru/daily_json.js"):
        self.cbr_url = cbr_url

    @classmethod
    def get_instance(cls) -> RateProvider:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_rates(self) -> CurrencyRates:
        if self._cache and self._last_update:
            if datetime.now() - self._last_update < timedelta(hours=1):
                return self._cache
        
        try:
            return await self._fetch_rates()
        except Exception as e:
            logger.error(f"Failed to fetch rates: {e}")
            # Fallback to hardcoded recent averages if API fails
            if self._cache:
                return self._cache
            return CurrencyRates(
                usd=90.0,
                eur=98.0,
                cny=12.5,
                updated_at=datetime.now()
            )

    async def _fetch_rates(self) -> CurrencyRates:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.cbr_url) as response:
                if response.status != 200:
                    raise ValueError(f"CBR API returned {response.status}")
                
                data = await response.json(content_type=None)
                valute = data.get("Valute", {})
                
                usd = float(valute.get("USD", {}).get("Value", 0.0))
                eur = float(valute.get("EUR", {}).get("Value", 0.0))
                cny = float(valute.get("CNY", {}).get("Value", 0.0))
                
                rates = CurrencyRates(
                    usd=usd,
                    eur=eur,
                    cny=cny,
                    updated_at=datetime.now()
                )
                
                self._cache = rates
                self._last_update = datetime.now()
                logger.info(f"Updated rates: USD={usd}, CNY={cny}")
                return rates
