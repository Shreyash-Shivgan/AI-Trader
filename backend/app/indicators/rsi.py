from __future__ import annotations

import pandas as pd
import ta


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
    rsi_indicator = ta.momentum.RSIIndicator(
        close=pd.to_numeric(df["close"], errors="coerce"), window=period
    )
    return round(float(rsi_indicator.rsi().iloc[-1]), 6)
