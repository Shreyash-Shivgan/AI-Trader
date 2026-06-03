from __future__ import annotations

import asyncio
import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal
from app.models.entities import Signal, Alert
from app.notifications.telegram import TelegramNotifier
from app.services.analysis_engine import AnalysisEngine
from app.services.market_data import market_data_service
from app.utils.formatting import generate_telegram_message

logger = logging.getLogger(__name__)


def _persist_signal(
    db, symbol: str, timeframe: str, analysis: dict[str, Any]
) -> Signal:
    trade_review = analysis.get("trade_review", {})
    setup = analysis.get("trade_setup", {})
    signal = Signal(
        symbol=symbol,
        timeframe=timeframe,
        direction=(setup.get("trade_side") or "wait"),
        confidence_score=float(trade_review.get("confidence_score", 0.0) or 0.0),
        status="formed",
        entry_price=setup.get("entry_price"),
        stop_loss=setup.get("stop_loss"),
        take_profit_1=setup.get("take_profit_1"),
        take_profit_2=setup.get("take_profit_2"),
        take_profit_3=setup.get("take_profit_3"),
        explanation=setup.get("trade_explanation"),
        setup_payload=setup,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def _persist_alert(
    db, signal_id: int | None, channel: str, alert_type: str, message: str
) -> Alert:
    alert = Alert(
        signal_id=signal_id,
        channel=channel,
        alert_type=alert_type,
        message=message,
        status="delivered",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def format_price(val: Any) -> str:
    try:
        f_val = float(val)
        if f_val.is_integer():
            return f"{int(f_val)}"
        return f"{f_val:.2f}"
    except (ValueError, TypeError):
        return str(val) if val is not None else "XXXX"


def _run_analysis_sync(symbol: str, timeframe: str = "5m") -> dict[str, Any]:
    # Run the async analysis engine from sync context
    async def _inner():
        # create a temporary DB session for AnalysisEngine
        db = SessionLocal()
        try:
            engine = AnalysisEngine(db=db, market_data_service=market_data_service)
            return await engine.analyze_symbol(symbol, timeframe, 10000.0, 1.0)
        finally:
            db.close()

    return asyncio.run(_inner())


class ScannerService:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        if not settings.scheduler_enabled:
            logger.info("Scheduler disabled by settings")
            return
        # Schedule scan every N seconds (configurable later); use 60s for now
        self.scheduler.add_job(self.scan_all, "interval", seconds=60, id="scan_all")
        self.scheduler.start()
        logger.info("ScannerService started")

    def shutdown(self) -> None:
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            pass
        logger.info("ScannerService stopped")

    def scan_all(self) -> None:
        logger.debug("ScannerService: scanning symbols")
        symbols = settings.default_symbols
        timeframes = settings.monitored_timeframes
        for symbol in symbols:
            for tf in timeframes:
                try:
                    analysis = _run_analysis_sync(symbol, tf)
                    review = analysis.get("trade_review", {})
                    if review.get("allowed_to_alert"):
                        db = SessionLocal()
                        try:
                            signal = _persist_signal(db, symbol, tf, analysis)
                            
                            # build alert message using the new graded layouts
                            trade_setup = analysis.get("trade_setup", {})
                            indicators = analysis.get("indicators", {})
                            smc = analysis.get("smart_money", {})
                            
                            price_val = float(indicators.get("latest_close", 0.0) or 0.0)
                            
                            side_val = str(trade_setup.get("trade_side", "buy")).lower()
                            direction_str = "BUY" if side_val == "buy" else "SELL"
                            
                            # Risk Reward
                            rr_val = float(trade_setup.get("risk_reward_ratio", 0.0) or 0.0)
                            
                            # Lot size
                            lot_val = float(trade_setup.get("lot_size", 0.0) or 0.0)

                            # Determine Grade and Quality
                            confidence = float(review.get("confidence_score", 0.0))
                            
                            def determine_grade(conf: float, rr: float) -> str:
                                if conf >= 85 and rr >= 3.0:
                                    return "A+"
                                if conf >= 75 and rr >= 2.5:
                                    return "A"
                                if conf >= 65 and rr >= 2.0:
                                    return "B"
                                if conf >= 50 and rr >= 1.2:
                                    return "C"
                                return "Speculative"

                            grade = determine_grade(confidence, rr_val)

                            atr_val = float(indicators.get("atr", 1.5) or 1.5)
                            entry_price_val = float(trade_setup.get("entry_price", 0.0) or 0.0)
                            stop_loss_val = float(trade_setup.get("stop_loss", 0.0) or 0.0)
                            tp1_val = float(trade_setup.get("take_profit_1", 0.0) or 0.0)
                            tp2_val = float(trade_setup.get("take_profit_2", 0.0) or 0.0)
                            tp3_val = float(trade_setup.get("take_profit_3", 0.0) or 0.0)
                            support_val = float(smc.get("support") or trade_setup.get("support") or 0.0)
                            resistance_val = float(smc.get("resistance") or trade_setup.get("resistance") or 0.0)

                            msg = generate_telegram_message(
                                symbol=symbol,
                                current_price=price_val,
                                entry_price=entry_price_val,
                                direction=direction_str,
                                stop_loss=stop_loss_val,
                                tp1=tp1_val,
                                tp2=tp2_val,
                                tp3=tp3_val,
                                rr=rr_val,
                                lot_size=lot_val,
                                grade=grade,
                                atr=atr_val,
                                support=support_val,
                                resistance=resistance_val,
                            )
                            notifier = TelegramNotifier()
                            try:
                                notifier.send_message_sync(msg)
                            except Exception:
                                logger.exception("Failed to send Telegram alert")
                            _persist_alert(
                                db, signal.id, "telegram", "high_confidence_setup", msg
                            )
                        finally:
                            db.close()
                except SQLAlchemyError:
                    logger.exception("DB error while scanning %s %s", symbol, tf)
                except Exception:
                    logger.exception("Unexpected error scanning %s %s", symbol, tf)


scanner_service = ScannerService()
