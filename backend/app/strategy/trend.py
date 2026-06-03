from __future__ import annotations

from typing import Any

import pandas as pd

from app.indicators.advanced import calculate_adx


def detect_trend(frame: pd.DataFrame) -> dict[str, Any]:
    ema20 = (
        frame["ema20"]
        if "ema20" in frame.columns
        else frame["close"].ewm(span=20, adjust=False).mean()
    )
    ema50 = (
        frame["ema50"]
        if "ema50" in frame.columns
        else frame["close"].ewm(span=50, adjust=False).mean()
    )
    ema200 = (
        frame["ema200"]
        if "ema200" in frame.columns
        else frame["close"].ewm(span=200, adjust=False).mean()
    )

    latest_close = float(frame["close"].iloc[-1])
    latest_ema20 = float(ema20.iloc[-1])
    latest_ema50 = float(ema50.iloc[-1])
    latest_ema200 = float(ema200.iloc[-1])
    adx = calculate_adx(frame)["adx"] if len(frame) >= 14 else 0.0

    bullish = latest_close > latest_ema20 > latest_ema50 > latest_ema200
    bearish = latest_close < latest_ema20 < latest_ema50 < latest_ema200

    if bullish and adx >= 25:
        label = "strong_bullish"
    elif bearish and adx >= 25:
        label = "strong_bearish"
    elif bullish:
        label = "bullish"
    elif bearish:
        label = "bearish"
    else:
        label = "sideways"

    strength = min(
        100.0,
        round(
            adx + abs(latest_ema20 - latest_ema50) / max(latest_close, 1e-6) * 1000.0, 2
        ),
    )
    return {
        "trend": label,
        "trend_strength_score": strength,
        "ema_alignment": {
            "ema20": round(latest_ema20, 6),
            "ema50": round(latest_ema50, 6),
            "ema200": round(latest_ema200, 6),
        },
        "adx": adx,
    }
