from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from telegram import Update

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
from app.telegram_bot import build_application

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database
    try:
        init_db()
    except Exception as exc:
        logger.warning("Database initialization skipped: %s", exc)
    else:
        # Start background scanner only when the DB is reachable
        scanner_service.start()

    # Initialize Telegram Bot
    telegram_app = None
    if settings.telegram_bot_token and os.getenv("RUN_BOT_IN_APP", "true").lower() == "true":
        try:
            logger.info("Initializing Telegram Bot...")
            telegram_app = build_application()
            await telegram_app.initialize()
            await telegram_app.start()

            render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
            if settings.environment == "production" and render_host:
                # Webhook Mode: Telegram will wake up the Render service on new messages
                webhook_url = f"https://{render_host}/webhook/telegram"
                logger.info(f"Configuring Telegram Webhook at: {webhook_url}")
                await telegram_app.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
            else:
                # Polling Mode: Ideal for local development
                logger.info("Starting Telegram Bot polling loop...")
                await telegram_app.updater.start_polling(drop_pending_updates=True)

            app.state.telegram_app = telegram_app
        except Exception as exc:
            logger.error("Failed to start Telegram Bot: %s", exc, exc_info=True)

    yield

    # Shutdown background scanner
    scanner_service.shutdown()

    # Shutdown Telegram Bot
    if telegram_app:
        try:
            logger.info("Stopping Telegram Bot...")
            if telegram_app.updater and telegram_app.updater.running:
                await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
            logger.info("Telegram Bot stopped successfully.")
        except Exception as exc:
            logger.error("Error during Telegram Bot shutdown: %s", exc, exc_info=True)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(market_router)
app.include_router(analysis_router)
app.include_router(signals_router)
app.include_router(trades_router)
app.include_router(performance_router)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Webhook endpoint for receiving Telegram updates in production.

    This wakes up the Render container instantly when a message is received.
    """
    telegram_app = getattr(request.app.state, "telegram_app", None)
    if not telegram_app:
        raise HTTPException(status_code=503, detail="Telegram bot is not initialized")

    try:
        payload = await request.json()
        update = Update.de_json(payload, telegram_app.bot)
        if update:
            await telegram_app.process_update(update)
    except Exception as exc:
        logger.error("Error processing Telegram update via webhook: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "ok"}


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
