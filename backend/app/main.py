from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Query

from app.config import settings
from app.database import init_db
from app.indicators.atr import calculate_atr
from app.indicators.ema import calculate_ema
from app.indicators.macd import calculate_macd
from app.indicators.rsi import calculate_rsi
from app.routes.analysis import router as analysis_router
from app.routes.market import router as market_router
from app.routes.performance import router as performance_router
from app.routes.signals import router as signals_router
from app.routes.trades import router as trades_router
from app.services.market_data import MarketDataError, market_data_service
from app.services.scanner import scanner_service

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


import threading
import os

def run_bot_in_background():
    from app.telegram_bot import main as bot_main
    try:
        bot_main()
    except Exception as exc:
        logging.error("Telegram bot background thread failed: %s", exc, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as exc:
        logging.warning("Database initialization skipped: %s", exc)
    else:
        # start background scanner only when the DB is reachable
        scanner_service.start()
        
    # Run bot in the same process/container if enabled
    if settings.telegram_bot_token and os.getenv("RUN_BOT_IN_APP", "true").lower() == "true":
        logging.info("Starting Telegram Bot in background thread...")
        threading.Thread(target=run_bot_in_background, daemon=True).start()
        
    yield
    # shutdown background scanner
    scanner_service.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(market_router)
app.include_router(analysis_router)
app.include_router(signals_router)
app.include_router(trades_router)
app.include_router(performance_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "running", "environment": settings.environment}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/market/{symbol}/analysis")
async def analyze_market(
    symbol: str,
    timeframe: str = Query(default="5m"),
    limit: int = Query(default=200, ge=50, le=1000),
) -> dict[str, object]:
    try:
        frame = await market_data_service.get_dataframe(symbol, timeframe, limit)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if frame.empty:
        raise HTTPException(status_code=404, detail="No market data returned")

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "latest_close": float(frame.iloc[-1]["close"]),
        "indicators": {
            **calculate_ema(frame),
            "rsi": calculate_rsi(frame),
            **calculate_macd(frame),
            "atr": calculate_atr(frame),
        },
    }
