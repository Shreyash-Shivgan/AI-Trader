from __future__ import annotations

import pandas as pd


def calculate_ema(df: pd.DataFrame) -> dict[str, float]:
    close = pd.to_numeric(df["close"], errors="coerce")
    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]

    return {
        "ema20": round(float(ema20), 6),
        "ema50": round(float(ema50), 6),
        "ema200": round(float(ema200), 6),
    }
