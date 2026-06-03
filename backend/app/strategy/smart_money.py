from __future__ import annotations

from typing import Any

import pandas as pd

from app.indicators.advanced import detect_swings, calculate_support_resistance


def detect_smart_money_concepts(frame: pd.DataFrame) -> dict[str, Any]:
    swings = detect_swings(frame)
    support_resistance = calculate_support_resistance(frame)
    latest_close = float(frame["close"].iloc[-1])
    latest_high = float(frame["high"].iloc[-1])
    latest_low = float(frame["low"].iloc[-1])

    bos = latest_close > support_resistance["resistance"]
    choch = latest_close < support_resistance["support"]
    liquidity_sweep = any(
        swing["price"] < latest_low for swing in swings.swing_lows[-3:]
    ) or any(swing["price"] > latest_high for swing in swings.swing_highs[-3:])
    premium_discount_zone = (
        "premium"
        if latest_close
        >= (support_resistance["support"] + support_resistance["resistance"]) / 2.0
        else "discount"
    )

    return {
        "bos": bos,
        "choch": choch,
        "liquidity_sweep": liquidity_sweep,
        "order_blocks": [],
        "fair_value_gaps": [],
        "mitigation_blocks": [],
        "premium_discount_zone": premium_discount_zone,
        "equal_highs": len(swings.swing_highs) >= 2
        and abs(swings.swing_highs[-1]["price"] - swings.swing_highs[-2]["price"])
        <= latest_close * 0.0005,
        "equal_lows": len(swings.swing_lows) >= 2
        and abs(swings.swing_lows[-1]["price"] - swings.swing_lows[-2]["price"])
        <= latest_close * 0.0005,
        "stop_hunt": liquidity_sweep,
        "institutional_footprint": bos or choch or liquidity_sweep,
        "swing_highs": swings.swing_highs,
        "swing_lows": swings.swing_lows,
        "support": support_resistance["support"],
        "resistance": support_resistance["resistance"],
    }
