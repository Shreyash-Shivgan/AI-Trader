from __future__ import annotations

import math
from typing import Any


def format_price(val: Any) -> str:
    try:
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            return "XXXX"
        if f_val.is_integer():
            return f"{int(f_val)}"
        return f"{f_val:.2f}"
    except (ValueError, TypeError):
        return str(val) if val is not None else "XXXX"


# ---------------------------------------------------------------------------
# Setup detection
# ---------------------------------------------------------------------------

def detect_setup_label(
    direction: str,
    entry_price: float,
    current_price: float,
    support: float,
    resistance: float,
    atr: float,
) -> str:
    """Return an institutional setup label based on price context."""
    dir_up = "BUY" in direction.upper()
    near_support = support > 0 and abs(entry_price - support) <= atr * 1.5
    near_resistance = resistance > 0 and abs(entry_price - resistance) <= atr * 1.5
    above_resistance = entry_price > resistance > 0
    below_support = entry_price < support > 0
    is_limit = abs(entry_price - current_price) > atr * 0.15

    if dir_up:
        if near_support and is_limit:
            return "Support Bounce"
        if above_resistance:
            return "Breakout Retest"
        if below_support:
            return "Discount Zone Buy"
        if is_limit:
            return "Order Block Retest"
        return "Trend Continuation"
    else:
        if near_resistance and is_limit:
            return "Resistance Retest"
        if below_support:
            return "Breakout Retest"
        if above_resistance:
            return "Premium Zone Sell"
        if is_limit:
            return "Liquidity Sweep"
        return "Trend Continuation"


# ---------------------------------------------------------------------------
# Confirmation rule
# ---------------------------------------------------------------------------

def detect_confirmation(direction: str, setup: str) -> str:
    """Return a specific M15/M5 confirmation rule."""
    dir_up = "BUY" in direction.upper()
    if dir_up:
        if "Bounce" in setup or "Discount" in setup or "Order Block" in setup:
            return "M15 Bullish Engulfing or Higher Low Formation"
        if "Breakout" in setup:
            return "M5 BOS Up + M15 Close Above Level"
        return "M15 Rejection Wick or M5 BOS Up"
    else:
        if "Retest" in setup or "Premium" in setup or "Sweep" in setup:
            return "M15 Bearish Engulfing or M15 Rejection Wick"
        if "Breakout" in setup:
            return "M5 BOS Down + M15 Close Below Level"
        return "M15 Bearish Engulfing or Lower High Formation"


# ---------------------------------------------------------------------------
# Trend label
# ---------------------------------------------------------------------------

def determine_reason(
    direction: str,
    entry_price: float,
    support: float,
    resistance: float,
    atr: float,
) -> str:
    """Legacy helper kept for scanner compatibility."""
    return detect_setup_label(direction, entry_price, entry_price, support, resistance, atr)


def trend_label(trend_raw: str, timeframe: str = "H1") -> str:
    t = trend_raw.lower()
    if "bull" in t:
        return f"{timeframe} Bullish 📈"
    if "bear" in t:
        return f"{timeframe} Bearish 📉"
    return f"{timeframe} Sideways ➡️"


# ---------------------------------------------------------------------------
# Grade helpers
# ---------------------------------------------------------------------------

def confidence_to_grade(conf: float, rr: float) -> str:
    if conf >= 90 and rr >= 3.0:
        return "A+"
    if conf >= 75 and rr >= 2.5:
        return "A"
    if conf >= 60 and rr >= 2.0:
        return "B"
    return "C"


# ---------------------------------------------------------------------------
# Core signal formatter  (institutional format)
# ---------------------------------------------------------------------------

def generate_telegram_message(
    symbol: str,
    current_price: float,
    entry_price: float,
    direction: str,           # "BUY" or "SELL"
    stop_loss: float,
    tp1: float,
    tp2: float,
    tp3: float,
    rr: float,
    lot_size: float,
    grade: str,               # "A+", "A", "B", "C"
    atr: float,
    support: float,
    resistance: float,
    reason: str = "",
    trend_raw: str = "",
    h4_trend_raw: str = "",
    confidence: float = 0.0,
) -> str:
    sym = symbol.replace("/", "").replace("_", "").upper()
    dir_upper = direction.upper()

    # Order type
    is_market = abs(entry_price - current_price) <= atr * 0.15
    if is_market:
        order_type = f"{dir_upper} NOW"
    else:
        order_type = f"{dir_upper} LIMIT"

    # Setup + confirmation
    setup_label = reason if reason else detect_setup_label(
        dir_upper, entry_price, current_price, support, resistance, atr
    )
    confirm_rule = detect_confirmation(dir_upper, setup_label)

    # RR string
    rr_str = f"1:{rr:.1f}" if rr > 0 else "1:?"

    # Confidence % + grade string
    conf_pct = int(round(confidence)) if confidence > 0 else None
    if conf_pct:
        conf_str = f"{conf_pct}% (Grade {grade})"
    else:
        conf_str = f"Grade {grade}"

    # Trend lines
    h1_trend = trend_label(trend_raw, "H1") if trend_raw else "H1 — 📊"
    h4_trend = trend_label(h4_trend_raw, "H4") if h4_trend_raw else None

    # Invalidation level
    inval = format_price(stop_loss)

    # Emoji
    emoji = "🚨"

    lines = [
        f"{emoji} {sym} | {order_type}",
        "",
        f"Entry: {format_price(entry_price)}",
        f"SL:    {format_price(stop_loss)}",
        "",
        f"TP1: {format_price(tp1)}",
        f"TP2: {format_price(tp2)}",
        f"TP3: {format_price(tp3)}",
        "",
        f"RR: {rr_str}",
        "",
        f"Trend: {h1_trend}",
    ]
    if h4_trend:
        lines.append(f"       {h4_trend}")

    lines += [
        "",
        "Setup:",
        setup_label,
        "",
        "Confirm:",
        confirm_rule,
        "",
        f"Confidence: {conf_str}",
        "",
        "Risk: 1% per trade",
        "",
        "Trade Plan:",
        "✅ Enter only after confirmation",
        "✅ Move SL to Breakeven at TP1",
        "✅ Take partial profit at TP1",
        f"❌ Cancel if price breaks {inval}",
    ]

    if grade == "C":
        lines.insert(lines.index("Risk: 1% per trade"), "⚠️  Low Confidence — Wait for Confirmation")
        lines.insert(lines.index("⚠️  Low Confidence — Wait for Confirmation") + 1, "")

    return "\n".join(lines)


def build_dual_signal(
    symbol: str,
    pref_msg: str,
    alt_msg: str,
) -> str:
    """Wrap preferred + alternative into the final dual-signal Telegram message."""
    return (
        f"📍 PREFERRED TRADE\n"
        f"{'─' * 30}\n"
        f"{pref_msg}\n"
        f"\n"
        f"📍 BEST ALTERNATIVE TRADE\n"
        f"{'─' * 30}\n"
        f"{alt_msg}"
    )
