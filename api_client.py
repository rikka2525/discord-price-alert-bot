"""Async client for CoinGecko's public price endpoint."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import aiohttp


class PriceAPIError(RuntimeError):
    """Raised when the external price service cannot return usable data."""


@dataclass(frozen=True)
class PriceResult:
    coin_id: str
    usd: float


class CoinGeckoClient:
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    async def get_prices(self, coin_ids: list[str]) -> dict[str, float]:
        unique_ids = sorted({coin_id.lower() for coin_id in coin_ids})
        if not unique_ids:
            return {}

        params = {"ids": ",".join(unique_ids), "vs_currencies": "usd"}
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with self.session.get(
                    f"{self.BASE_URL}/simple/price",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 429 or response.status >= 500:
                        raise PriceAPIError(f"temporary API error: HTTP {response.status}")
                    if response.status != 200:
                        raise PriceAPIError(f"price API returned HTTP {response.status}")
                    payload = await response.json()
                    return {
                        coin_id: float(data["usd"])
                        for coin_id, data in payload.items()
                        if isinstance(data, dict) and data.get("usd") is not None
                    }
            except (aiohttp.ClientError, asyncio.TimeoutError, PriceAPIError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(2**attempt)

        raise PriceAPIError("price API is temporarily unavailable") from last_error

    async def get_price(self, coin_id: str) -> PriceResult:
        normalized = coin_id.strip().lower()
        prices = await self.get_prices([normalized])
        if normalized not in prices:
            raise PriceAPIError(f"unknown coin id: {normalized}")
        return PriceResult(coin_id=normalized, usd=prices[normalized])
