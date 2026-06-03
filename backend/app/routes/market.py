from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.market_data import MarketDataError, market_data_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/{symbol}/snapshot")
async def snapshot(
    symbol: str, timeframe: str = Query(default="5m")
) -> dict[str, object]:
    try:
        return await market_data_service.get_symbol_snapshot(symbol, timeframe)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/candles")
async def candles(
    symbol: str,
    timeframe: str = Query(default="5m"),
    limit: int = Query(default=200, ge=20, le=1000),
) -> dict[str, object]:
    try:
        frame = await market_data_service.get_dataframe(symbol, timeframe, limit)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": frame.to_dict(orient="records"),
    }
