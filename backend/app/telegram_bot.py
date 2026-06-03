from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import settings
from app.risks.manager import RiskManager
from app.services.market_data import MarketDataError, market_data_service
from app.services.analysis_engine import AnalysisEngine
from app.database import SessionLocal

from sqlalchemy.orm import Session
from app.utils.formatting import format_price, generate_telegram_message, determine_reason, build_dual_signal



logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("AI Trader Online\n\nUse /analyze XAUUSD")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/start\n/help\n/analyze XAUUSD\n/watch XAUUSD\n/unwatch XAUUSD\n/report\n/risk balance riskpercent\n/opentrades\n/history\n/status"
    )


# format_price is imported from app.utils.formatting


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symbol = context.args[0].upper() if context.args else "XAUUSD"
    symbol = symbol if "/" in symbol else f"{symbol[:3]}/{symbol[3:]}"
    # Create a DB session for the analysis engine (closed after use)
    db: Session | None = None
    try:
        db = SessionLocal()
        engine = AnalysisEngine(db=db, market_data_service=market_data_service)
        result = await engine.analyze_symbol(symbol, "5m", 10000.0, 1.0)
    except MarketDataError as exc:
        logger.error(f"[Telegram Bot] MarketDataError in analyze: {exc}", exc_info=True)
        await update.message.reply_text(f"❌ Market data error:\n<code>{exc}</code>", parse_mode="HTML")
        return
    except Exception as exc:
        logger.error(f"[Telegram Bot] Exception in analyze: {exc}", exc_info=True)
        await update.message.reply_text(f"❌ Analysis error:\n<code>{type(exc).__name__}: {exc}</code>", parse_mode="HTML")
        return

    finally:
        if db is not None:
            db.close()

    review = result.get("trade_review", {})
    map_data = result.get("confluence_map", {})
    trend = result.get("trend", {})
    session = result.get("session", {})
    smc = result.get("smart_money", {})
    critic = result.get("critic", {})
    trade_setup = result.get("trade_setup", {})

    approved = bool(review.get("approved"))

    # Format Trend
    trend_raw = str(trend.get("trend", "sideways")).lower()
    if "bull" in trend_raw:
        trend_label = "Bullish"
    elif "bear" in trend_raw:
        trend_label = "Bearish"
    else:
        trend_label = "Sideways"

    # Support / Resistance values
    resistance_val = smc.get("resistance") or trade_setup.get("resistance") or "XXXX"
    support_val = smc.get("support") or trade_setup.get("support") or "XXXX"

    current_price = result.get("indicators", {}).get("latest_close", 0.0)
    if current_price is None or current_price <= 0:
        current_price = float(trade_setup.get("entry_price", 0.0))

    logger.info(
        f"[Telegram Output Log] analyze: Symbol={symbol}, Current Price={current_price}, "
        f"Support={support_val}, Resistance={resistance_val}, Approved={approved}"
    )

    symbol_header = symbol.replace("/", "")
    current_price_str = format_price(current_price)

    # Expected direction
    side_val = review.get("side", "").lower()
    if side_val not in {"buy", "sell"}:
        side_val = "buy" if "bull" in trend_raw else "sell"
    expected_direction = "Bullish" if side_val == "buy" else "Bearish"

    # Risk Reward
    pref_setup = result.get("preferred_setup", trade_setup)
    alt_setup = result.get("alternative_setup", trade_setup)

    atr = float(result.get("indicators", {}).get("atr", 1.5) or 1.5)
    confidence = float(review.get("confidence_score", map_data.get("confidence_score", 0.0)) or 0.0)

    try:
        support_f = float(support_val)
    except (ValueError, TypeError):
        support_f = current_price

    try:
        resistance_f = float(resistance_val)
    except (ValueError, TypeError):
        resistance_f = current_price

    def determine_grade(conf: float, rr: float) -> str:
        if conf < settings.confidence_threshold:
            return "C"
        if conf >= 85 and rr >= 3.0:
            return "A+"
        if conf >= 75 and rr >= 2.5:
            return "A"
        if conf >= 65 and rr >= 2.0:
            return "B"
        return "C"

    # Preferred Setup details
    pref_side = str(pref_setup.get("trade_side", "buy")).lower()
    pref_dir_str = "BUY" if pref_side == "buy" else "SELL"
    pref_entry = float(pref_setup.get("entry_price", 0.0) or 0.0)
    pref_sl = float(pref_setup.get("stop_loss", 0.0) or 0.0)
    pref_tp1 = float(pref_setup.get("take_profit_1", 0.0) or 0.0)
    pref_tp2 = float(pref_setup.get("take_profit_2", 0.0) or 0.0)
    pref_tp3 = float(pref_setup.get("take_profit_3", 0.0) or 0.0)
    pref_rr = float(pref_setup.get("risk_reward_ratio", 0.0) or 0.0)
    pref_lot = float(pref_setup.get("lot_size", 0.0) or 0.0)
    pref_grade = determine_grade(confidence, pref_rr)
    pref_reason = determine_reason(pref_dir_str, pref_entry, support_f, resistance_f, atr)

    pref_msg = generate_telegram_message(
        symbol=symbol_header,
        current_price=current_price,
        entry_price=pref_entry,
        direction=pref_dir_str,
        stop_loss=pref_sl,
        tp1=pref_tp1,
        tp2=pref_tp2,
        tp3=pref_tp3,
        rr=pref_rr,
        lot_size=pref_lot,
        grade=pref_grade,
        atr=atr,
        support=support_f,
        resistance=resistance_f,
        reason=pref_reason,
        trend_raw=trend_raw,
        confidence=confidence,
    )

    # Alternative Setup details
    alt_side = str(alt_setup.get("trade_side", "sell")).lower()
    alt_dir_str = "BUY" if alt_side == "buy" else "SELL"
    alt_entry = float(alt_setup.get("entry_price", 0.0) or 0.0)
    alt_sl = float(alt_setup.get("stop_loss", 0.0) or 0.0)
    alt_tp1 = float(alt_setup.get("take_profit_1", 0.0) or 0.0)
    alt_tp2 = float(alt_setup.get("take_profit_2", 0.0) or 0.0)
    alt_tp3 = float(alt_setup.get("take_profit_3", 0.0) or 0.0)
    alt_rr = float(alt_setup.get("risk_reward_ratio", 0.0) or 0.0)
    alt_lot = float(alt_setup.get("lot_size", 0.0) or 0.0)
    alt_grade = determine_grade(confidence, alt_rr)
    alt_reason = determine_reason(alt_dir_str, alt_entry, support_f, resistance_f, atr)

    # Alt trend is opposite
    alt_trend_raw = "bearish" if "bull" in trend_raw else "bullish"

    alt_msg = generate_telegram_message(
        symbol=symbol_header,
        current_price=current_price,
        entry_price=alt_entry,
        direction=alt_dir_str,
        stop_loss=alt_sl,
        tp1=alt_tp1,
        tp2=alt_tp2,
        tp3=alt_tp3,
        rr=alt_rr,
        lot_size=alt_lot,
        grade=alt_grade,
        atr=atr,
        support=support_f,
        resistance=resistance_f,
        reason=alt_reason,
        trend_raw=alt_trend_raw,
        confidence=confidence,
    )

    final_message = build_dual_signal(symbol_header, pref_msg, alt_msg)
    await update.message.reply_text(final_message)



async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symbol = context.args[0].upper() if context.args else "XAUUSD"
    await update.message.reply_text(f"Watchlist updated for {symbol}")


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symbol = context.args[0].upper() if context.args else "XAUUSD"
    await update.message.reply_text(f"Watchlist removed for {symbol}")


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Daily market report scheduling is enabled in the backend; add the scheduler job to begin publishing reports."
    )


async def risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /risk balance riskpercent")
        return
    account_balance = float(context.args[0])
    risk_percent = float(context.args[1])
    metrics = RiskManager().calculate(account_balance, risk_percent, 1.0, 2.0, None)
    if metrics.lot_size <= 0:
        lot_size_str = "N/A\n\nReason:\nUnable to calculate position size."
    else:
        lot_size_str = f"{metrics.lot_size:.4f}"
    await update.message.reply_text(
        f"Risk Amount: {metrics.risk_amount:.2f}\nLot Size:\n{lot_size_str}\nRR: {metrics.rr_ratio:.2f}"
    )


async def open_trades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Open trades are exposed through the API; the persistence layer will populate them once trade execution is enabled."
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Trade history is available through the API; no trade records are persisted yet."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Environment: {settings.environment}\nSymbols: {', '.join(settings.default_symbols)}\nTimeframes: {', '.join(settings.monitored_timeframes)}"
    )


def build_application() -> Application:
    token = settings.telegram_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("analyze", analyze))
    application.add_handler(CommandHandler("watch", watch))
    application.add_handler(CommandHandler("unwatch", unwatch))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("risk", risk))
    application.add_handler(CommandHandler("opentrades", open_trades))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("status", status))
    return application


def main() -> None:
    application = build_application()
    logger.info("Telegram bot starting")
    application.run_polling()


if __name__ == "__main__":
    main()
