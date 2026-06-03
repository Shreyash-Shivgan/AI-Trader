from __future__ import annotations

from typing import Any

import pandas as pd

from app.risks.manager import RiskManager


def _round_lot_size(
    lot_size: float, step: float = 0.01, minimum: float = 0.01
) -> float:
    if lot_size <= 0:
        return 0.0
    rounded = round(round(lot_size / step) * step, 2)
    return rounded if rounded >= minimum else minimum


def generate_trade_setup(
    frame: pd.DataFrame,
    direction: str,
    confidence_score: float,
    account_balance: float,
    risk_percent: float,
) -> dict[str, Any]:
    latest_close_val = frame["close"].iloc[-1]
    if latest_close_val is None:
        raise ValueError("Current market price missing")
    import math
    try:
        latest_close = float(latest_close_val)
    except (ValueError, TypeError):
        raise ValueError("Invalid current market price received")
    if latest_close <= 0:
        raise ValueError("Invalid current market price received")
    if math.isnan(latest_close):
        raise ValueError("Current market price is NaN")
    atr = (
        float((frame["high"] - frame["low"]).rolling(14).mean().iloc[-1])
        if len(frame) >= 14
        else latest_close * 0.005
    )
    support = float(frame["low"].tail(20).min())
    resistance = float(frame["high"].tail(20).max())
    fib_low = float(frame["low"].min())
    fib_high = float(frame["high"].max())
    fib_diff = fib_high - fib_low
    fib_382 = fib_high - fib_diff * 0.382
    fib_500 = fib_high - fib_diff * 0.5
    fib_618 = fib_high - fib_diff * 0.618
    retracement_candidates = [fib_382, fib_500, fib_618]

    if direction.lower() in {"bullish", "buy", "long"}:
        pullback_entry = min(
            [latest_close, support + atr * 0.35, *retracement_candidates]
        )
        entry_price = max(support, pullback_entry)
        stop_loss = support - atr * 0.9
        take_profit_1 = max(resistance, entry_price + atr * 2.0)
        take_profit_2 = max(take_profit_1 + atr * 1.0, entry_price + atr * 3.0)
        take_profit_3 = max(take_profit_2 + atr * 1.0, entry_price + atr * 4.0)
        side = "buy"
    else:
        pullback_entry = max(
            [latest_close, resistance - atr * 0.35, *retracement_candidates]
        )
        entry_price = min(resistance, pullback_entry)
        stop_loss = resistance + atr * 0.9
        take_profit_1 = min(support, entry_price - atr * 2.0)
        take_profit_2 = min(take_profit_1 - atr * 1.0, entry_price - atr * 3.0)
        take_profit_3 = min(take_profit_2 - atr * 1.0, entry_price - atr * 4.0)
        side = "sell"

    risk_manager = RiskManager()
    risk = risk_manager.calculate(
        account_balance=account_balance,
        risk_percent=risk_percent,
        stop_loss_distance=abs(entry_price - stop_loss),
        take_profit_distance=abs(take_profit_1 - entry_price),
        entry_price=entry_price,
    )
    rounded_lot_size = _round_lot_size(risk.lot_size)

    explanation = (
        f"{direction.title()} setup on {side.upper()} bias. "
        f"Close={latest_close:.4f}, Support={support:.4f}, Resistance={resistance:.4f}, ATR={atr:.4f}."
    )

    return {
        "entry_price": round(entry_price, 6),
        "entry_zone": [
            round(entry_price - atr * 0.15, 6),
            round(entry_price + atr * 0.15, 6),
        ],
        "stop_loss": round(stop_loss, 6),
        "take_profit_1": round(take_profit_1, 6),
        "take_profit_2": round(take_profit_2, 6),
        "take_profit_3": round(take_profit_3, 6),
        "risk_reward_ratio": round(risk.rr_ratio, 2),
        "confidence_score": round(confidence_score, 2),
        "position_size": risk.position_size,
        "lot_size": rounded_lot_size,
        "raw_lot_size": round(risk.lot_size, 6),
        "risk_amount": risk.risk_amount,
        "trade_side": side,
        "trade_explanation": explanation,
        "support": round(support, 6),
        "resistance": round(resistance, 6),
        "fib_382": round(fib_382, 6),
        "fib_500": round(fib_500, 6),
        "fib_618": round(fib_618, 6),
    }
