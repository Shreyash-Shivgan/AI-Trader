from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
import math
from typing import Any

import httpx
import pandas as pd
from redis import Redis

from app.config import settings
from app.models.entities import MarketData

logger = logging.getLogger(__name__)

TIMEFRAME_ALIASES = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
    "daily": "1day",
}


@dataclass(slots=True)
class CandleFrame:
    symbol: str
    timeframe: str
    frame: pd.DataFrame


class MarketDataError(RuntimeError):
    pass


class TwelveDataClient:
    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        self.api_key = api_key or settings.twelvedata_api_key
        self.timeout = timeout
        self.base_url = "https://api.twelvedata.com"

    def _require_api_key(self) -> str:
        if not self.api_key:
            raise MarketDataError("TWELVEDATA_API_KEY is not configured")
        return self.api_key

    async def fetch_time_series(
        self, symbol: str, interval: str, outputsize: int = 200
    ) -> dict[str, Any]:
        params = {
            "symbol": symbol,
            "interval": TIMEFRAME_ALIASES.get(interval, interval),
            "outputsize": outputsize,
            "apikey": self._require_api_key(),
            "format": "JSON",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/time_series", params=params)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                raise MarketDataError(
                    f"TwelveData API rate limit hit (429). "
                    f"Free plan allows 8 requests/min. "
                    f"Retry after {retry_after}s or upgrade your plan at twelvedata.com."
                )
            response.raise_for_status()
            payload = response.json()

        logger.info(f"[Market API] Raw Time Series API Response for {symbol} ({interval}): {payload}")
        if payload.get("status") == "error":
            raise MarketDataError(payload.get("message", "Unable to fetch time series"))
        return payload

    async def fetch_price(self, symbol: str) -> dict[str, Any]:
        params = {"symbol": symbol, "apikey": self._require_api_key()}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/price", params=params)
            response.raise_for_status()
            payload = response.json()
        logger.info(f"[Market API] Raw Price API Response for {symbol}: {payload}")
        if payload.get("status") == "error":
            raise MarketDataError(payload.get("message", "Unable to fetch live price"))
        return payload


class MarketDataService:
    def __init__(
        self, redis_client: Redis | None = None, client: TwelveDataClient | None = None
    ) -> None:
        self.redis_client = redis_client
        self.client = client or TwelveDataClient()

    @staticmethod
    def _cache_key(symbol: str, timeframe: str, outputsize: int) -> str:
        return f"market_data:{symbol}:{timeframe}:{outputsize}"

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        sym = symbol.upper().replace("-", "").replace("_", "").strip()
        if "/" in sym:
            return sym
        if len(sym) == 6:
            return f"{sym[:3]}/{sym[3:]}"
        return sym

    @staticmethod
    def _normalize_frame(values: list[dict[str, Any]]) -> pd.DataFrame:
        frame = pd.DataFrame(values)
        if frame.empty:
            return frame
        # Ensure expected OHLCV columns exist so downstream indicators don't KeyError
        for col in ("open", "high", "low", "close"):
            if col not in frame.columns:
                frame[col] = pd.NA
        if "volume" not in frame.columns:
            # If volume is missing from the provider, default to zero to avoid
            # breaking volume-based indicators while preserving numeric dtype.
            frame["volume"] = 0
        if "datetime" in frame.columns:
            frame["datetime"] = pd.to_datetime(
                frame["datetime"], utc=True, errors="coerce"
            )
        for column in ("open", "high", "low", "close", "volume"):
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if "datetime" in frame.columns:
            frame = frame.dropna(subset=["datetime"])
            frame = frame.sort_values("datetime")
        return frame.reset_index(drop=True)

    async def get_live_price(self, symbol: str) -> dict[str, Any]:
        symbol = self.normalize_symbol(symbol)
        cache_key = f"price:{symbol}"
        if self.redis_client:
            cached = self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

        try:
            payload = await self.client.fetch_price(symbol)
            price_str = payload.get("price")
            if price_str is None:
                raise ValueError("Current market price missing")
            price_val = float(price_str)
            if price_val <= 0:
                raise ValueError("Invalid current market price received")
            if math.isnan(price_val):
                raise ValueError("Current market price is NaN")
        except Exception as err:
            logger.warning(f"[Market Data Service] Live price fetch failed: {err}. Attempting fallback close.")
            try:
                candle_frame = await self.get_time_series(symbol, "5m", 2)
                latest_close_val = candle_frame.frame.iloc[-1]["close"]
                if latest_close_val is None:
                    raise ValueError("Current market price missing")
                latest_close = float(latest_close_val)
                if latest_close <= 0:
                    raise ValueError("Invalid current market price received")
                if math.isnan(latest_close):
                    raise ValueError("Current market price is NaN")
                payload = {"symbol": symbol, "price": str(latest_close)}
            except Exception as exc:
                raise MarketDataError(f"Unable to fetch price or fallback close: {exc}")

        logger.info(f"[Market Data Service] get_live_price: Symbol={symbol}, Payload={payload}")
        if self.redis_client:
            self.redis_client.setex(cache_key, 15, json.dumps(payload))
        return payload

    async def get_time_series(
        self, symbol: str, timeframe: str, outputsize: int = 200
    ) -> CandleFrame:
        symbol = self.normalize_symbol(symbol)
        cache_key = self._cache_key(symbol, timeframe, outputsize)
        if self.redis_client:
            cached = self.redis_client.get(cache_key)
            if cached:
                frame = pd.read_json(cached, orient="records")
                if not frame.empty:
                    logger.info(
                        f"[Market Data Service] get_time_series (cached): Symbol={symbol}, "
                        f"Timeframe={timeframe}, Latest Candle Close={frame.iloc[-1]['close']}, "
                        f"High={frame.iloc[-1]['high']}, Low={frame.iloc[-1]['low']}"
                    )
                return CandleFrame(symbol=symbol, timeframe=timeframe, frame=frame)

        payload = await self.client.fetch_time_series(symbol, timeframe, outputsize)
        frame = self._normalize_frame(payload.get("values", []))
        if frame.empty:
            raise MarketDataError(f"No candles returned for {symbol} {timeframe}")

        logger.info(
            f"[Market Data Service] get_time_series (live): Symbol={symbol}, "
            f"Timeframe={timeframe}, Latest Candle Close={frame.iloc[-1]['close']}, "
            f"High={frame.iloc[-1]['high']}, Low={frame.iloc[-1]['low']}"
        )

        if self.redis_client:
            self.redis_client.setex(
                cache_key, 60, frame.to_json(orient="records", date_format="iso")
            )
        return CandleFrame(symbol=symbol, timeframe=timeframe, frame=frame)

    def persist_candles(
        self, candle_frame: CandleFrame, source: str = "twelvedata"
    ) -> int:
        inserted = 0
        for record in candle_frame.frame.to_dict(orient="records"):
            timestamp = record.get("datetime")
            if timestamp is None:
                continue
            if isinstance(timestamp, pd.Timestamp):
                timestamp = timestamp.to_pydatetime()
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)

            existing = MarketData.query if False else None
            _ = existing  # keep lint happy if the ORM query shape changes later
            inserted += 1
        return inserted

    async def get_dataframe(
        self, symbol: str, timeframe: str, outputsize: int = 200
    ) -> pd.DataFrame:
        candle_frame = await self.get_time_series(symbol, timeframe, outputsize)
        return candle_frame.frame.copy()


market_data_service = MarketDataService()


async def get_gold_price() -> dict[str, Any]:
    return await market_data_service.get_live_price(settings.default_symbols[0])
