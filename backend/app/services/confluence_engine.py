from __future__ import annotations

from typing import Any

from app.config import settings
from app.notifications.telegram import TelegramNotifier
from app.utils.formatting import generate_telegram_message, determine_reason


def map_market_bias(score: float) -> str:
    if score >= 85:
        return "strong_bullish"
    if score >= 70:
        return "bullish"
    if score >= 40:
        return "neutral"
    if score >= 20:
        return "bearish"
    return "strong_bearish"


def map_momentum(indicators: dict[str, Any]) -> str:
    # Use momentum and macd histogram as heuristics
    momentum = float(indicators.get("momentum", 0.0))
    atr = float(indicators.get("atr", 0.0)) or 1e-6
    mag = abs(momentum)
    if mag >= atr * 2:
        return "strong"
    if mag >= atr:
        return "medium"
    return "weak"


def map_volatility(indicators: dict[str, Any], price: float) -> str:
    atr = float(indicators.get("atr", 0.0))
    if price <= 0:
        return "low"
    atr_pct = atr / price
    if atr_pct >= 0.02:
        return "high"
    if atr_pct >= 0.005:
        return "medium"
    return "low"


def format_price(val: Any) -> str:
    try:
        f_val = float(val)
        if f_val.is_integer():
            return f"{int(f_val)}"
        return f"{f_val:.2f}"
    except (ValueError, TypeError):
        return str(val) if val is not None else "XXXX"


def evaluate_confluence(
    symbol: str,
    indicators: dict[str, Any],
    trend: dict[str, Any],
    smc: dict[str, Any],
    confluence: Any,
    trade_setup: dict[str, Any],
    critic: dict[str, Any],
    trade_review: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
    alternative_setup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Accept either the ConfluenceScore dataclass or a dict
    if hasattr(confluence, "get"):
        score = float(confluence.get("total", 0.0) or 0.0)
        passed = bool(confluence.get("passed", False))
    else:
        # dataclass-like access
        score = float(getattr(confluence, "total", 0.0) or 0.0)
        passed = bool(getattr(confluence, "passed", False))
    price = float(indicators.get("close", indicators.get("latest_close", 0.0)) or 0.0)

    bias = map_market_bias(score)
    momentum = map_momentum(indicators)
    volatility = map_volatility(indicators, price)

    recommendation = "NO TRADE"
    if trade_review:
        recommendation = trade_review.get("institutional_recommendation", "NO TRADE")

    result = {
        "market_bias": bias,
        "confidence_score": round(score, 2),
        "momentum": momentum,
        "volatility": volatility,
        "trade_recommendation": recommendation,
        "nearest_support": smc.get("support"),
        "nearest_resistance": smc.get("resistance"),
        "potential_pullback_zone": [
            float(trade_setup.get("take_profit_1", 0.0)),
            float(trade_setup.get("take_profit_2", 0.0)),
        ],
        "entry_zone": trade_setup.get("entry_zone"),
        "stop_loss": trade_setup.get("stop_loss"),
        "take_profit_1": trade_setup.get("take_profit_1"),
        "take_profit_2": trade_setup.get("take_profit_2"),
        "take_profit_3": trade_setup.get("take_profit_3"),
        "rr": trade_setup.get("risk_reward_ratio"),
        "approved": bool(trade_review.get("approved")) if trade_review else bool(critic.get("approved", False) and passed),
    }

    try:
        allowed_to_alert = bool(trade_review and trade_review.get("allowed_to_alert"))
        if (
            result["confidence_score"] >= settings.confidence_threshold
            and settings.telegram_enabled
            and allowed_to_alert
        ):
            notifier = TelegramNotifier()
            price_val = float(indicators.get("latest_close", indicators.get("close", 0.0)) or 0.0)
            
            symbol_header = symbol.replace("/", "")
            current_price_str = format_price(price_val)
            
            side_val = str(trade_setup.get("trade_side", "buy")).lower()
            direction_str = "BUY" if side_val == "buy" else "SELL"
            
            entry_str = format_price(trade_setup.get("entry_price"))
            stop_loss_str = format_price(trade_setup.get("stop_loss"))
            tp_str = format_price(trade_setup.get("take_profit_1"))
            tp1_str = format_price(trade_setup.get("take_profit_1"))
            tp2_str = format_price(trade_setup.get("take_profit_2"))
            tp3_str = format_price(trade_setup.get("take_profit_3"))
            
            # Risk Reward
            rr_val = float(trade_setup.get("risk_reward_ratio", 0.0) or 0.0)
            rr_str = f"1:{rr_val:.1f}" if rr_val else "1:0.0"
            
            # Classification (Critical Fix 5)
            if rr_val <= 1.8:
                trade_type = "SCALP"
            elif rr_val <= 3.0:
                trade_type = "INTRADAY"
            else:
                trade_type = "SWING"
                
            # Lot size (Critical Fix 3)
            lot_val = float(trade_setup.get("lot_size", 0.0) or 0.0)

            alt_setup = alternative_setup or trade_setup

            # Determine Grade and Quality
            confidence = float(result.get("confidence_score", 0.0))
            
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

            atr_val = float(indicators.get("atr", 1.5) or 1.5)
            support_val = float(smc.get("support") or trade_setup.get("support") or price_val)
            resistance_val = float(smc.get("resistance") or trade_setup.get("resistance") or price_val)

            # Preferred Setup
            pref_side = str(trade_setup.get("trade_side", "buy")).lower()
            pref_dir_str = "BUY" if pref_side == "buy" else "SELL"
            pref_entry = float(trade_setup.get("entry_price", 0.0) or 0.0)
            pref_sl = float(trade_setup.get("stop_loss", 0.0) or 0.0)
            pref_tp1 = float(trade_setup.get("take_profit_1", 0.0) or 0.0)
            pref_tp2 = float(trade_setup.get("take_profit_2", 0.0) or 0.0)
            pref_tp3 = float(trade_setup.get("take_profit_3", 0.0) or 0.0)
            pref_grade = determine_grade(confidence, rr_val)
            pref_reason = determine_reason(pref_dir_str, pref_entry, support_val, resistance_val, atr_val)

            pref_msg = generate_telegram_message(
                symbol=symbol,
                current_price=price_val,
                entry_price=pref_entry,
                direction=pref_dir_str,
                stop_loss=pref_sl,
                tp1=pref_tp1,
                tp2=pref_tp2,
                tp3=pref_tp3,
                rr=rr_val,
                lot_size=lot_val,
                grade=pref_grade,
                atr=atr_val,
                support=support_val,
                resistance=resistance_val,
                reason=pref_reason,
            )

            # Alternative Setup
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
            alt_reason = determine_reason(alt_dir_str, alt_entry, support_val, resistance_val, atr_val)

            alt_msg = generate_telegram_message(
                symbol=symbol,
                current_price=price_val,
                entry_price=alt_entry,
                direction=alt_dir_str,
                stop_loss=alt_sl,
                tp1=alt_tp1,
                tp2=alt_tp2,
                tp3=alt_tp3,
                rr=alt_rr,
                lot_size=alt_lot,
                grade=alt_grade,
                atr=atr_val,
                support=support_val,
                resistance=resistance_val,
                reason=alt_reason,
            )

            final_message = (
                f"PREFERRED TRADE\n"
                f"{pref_msg}\n"
                f"\n"
                f"---\n"
                f"\n"
                f"BEST ALTERNATIVE TRADE\n"
                f"{alt_msg}"
            )
            notifier.send_message_sync(final_message)
    except Exception:
        # Never raise from notifier in the analysis pipeline
        pass

    return result
