from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import ta


@dataclass(slots=True)
class SwingPoints:
    swing_highs: list[dict[str, Any]]
    swing_lows: list[dict[str, Any]]


def calculate_bollinger_bands(
    frame: pd.DataFrame, window: int = 20, num_std: float = 2.0
) -> dict[str, float]:
    indicator = ta.volatility.BollingerBands(
        close=frame["close"].astype(float), window=window, window_dev=num_std
    )
    return {
        "bb_upper": round(float(indicator.bollinger_hband().iloc[-1]), 6),
        "bb_middle": round(float(indicator.bollinger_mavg().iloc[-1]), 6),
        "bb_lower": round(float(indicator.bollinger_lband().iloc[-1]), 6),
        "bb_width": round(float(indicator.bollinger_wband().iloc[-1]), 6),
    }


def calculate_vwap(frame: pd.DataFrame) -> float:
    price = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    volume = frame["volume"].fillna(0).astype(float)
    cumulative_volume = volume.cumsum().replace(0, np.nan)
    vwap = (price.astype(float) * volume).cumsum() / cumulative_volume
    return round(float(vwap.iloc[-1]), 6)


def calculate_adx(frame: pd.DataFrame, window: int = 14) -> dict[str, float]:
    indicator = ta.trend.ADXIndicator(
        high=frame["high"].astype(float),
        low=frame["low"].astype(float),
        close=frame["close"].astype(float),
        window=window,
    )
    return {
        "adx": round(float(indicator.adx().iloc[-1]), 6),
        "adx_pos": round(float(indicator.adx_pos().iloc[-1]), 6),
        "adx_neg": round(float(indicator.adx_neg().iloc[-1]), 6),
    }


def calculate_stochastic_rsi(
    frame: pd.DataFrame, window: int = 14, smooth1: int = 3, smooth2: int = 3
) -> dict[str, float]:
    indicator = ta.momentum.StochRSIIndicator(
        close=frame["close"].astype(float),
        window=window,
        smooth1=smooth1,
        smooth2=smooth2,
    )
    return {
        "stoch_rsi": round(float(indicator.stochrsi().iloc[-1]), 6),
        "stoch_rsi_k": round(float(indicator.stochrsi_k().iloc[-1]), 6),
        "stoch_rsi_d": round(float(indicator.stochrsi_d().iloc[-1]), 6),
    }


def calculate_ichimoku(frame: pd.DataFrame) -> dict[str, float]:
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    close = frame["close"].astype(float)

    tenkan_sen = (high.rolling(9).max() + low.rolling(9).min()) / 2.0
    kijun_sen = (high.rolling(26).max() + low.rolling(26).min()) / 2.0
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2.0).shift(26)
    senkou_span_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2.0).shift(26)
    chikou_span = close.shift(-26)

    return {
        "ichimoku_tenkan": round(float(tenkan_sen.iloc[-1]), 6),
        "ichimoku_kijun": round(float(kijun_sen.iloc[-1]), 6),
        "ichimoku_span_a": (
            round(float(senkou_span_a.iloc[-1]), 6)
            if not np.isnan(senkou_span_a.iloc[-1])
            else float("nan")
        ),
        "ichimoku_span_b": (
            round(float(senkou_span_b.iloc[-1]), 6)
            if not np.isnan(senkou_span_b.iloc[-1])
            else float("nan")
        ),
        "ichimoku_chikou": (
            round(float(chikou_span.iloc[-1]), 6)
            if not np.isnan(chikou_span.iloc[-1])
            else float("nan")
        ),
    }


def calculate_cci(frame: pd.DataFrame, window: int = 20) -> float:
    indicator = ta.trend.CCIIndicator(
        high=frame["high"].astype(float),
        low=frame["low"].astype(float),
        close=frame["close"].astype(float),
        window=window,
    )
    return round(float(indicator.cci().iloc[-1]), 6)


def calculate_momentum(frame: pd.DataFrame, window: int = 10) -> float:
    return round(float(frame["close"].astype(float).diff(window).iloc[-1]), 6)


def calculate_roc(frame: pd.DataFrame, window: int = 12) -> float:
    return round(
        float(frame["close"].astype(float).pct_change(periods=window).iloc[-1] * 100.0),
        6,
    )


def calculate_obv(frame: pd.DataFrame) -> float:
    close = frame["close"].astype(float)
    volume = frame["volume"].fillna(0).astype(float)
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * volume).cumsum()
    return round(float(obv.iloc[-1]), 6)


def calculate_volume_analysis(frame: pd.DataFrame) -> dict[str, float]:
    volume = frame["volume"].fillna(0).astype(float)
    rolling_mean = volume.rolling(20).mean()
    return {
        "volume_latest": round(float(volume.iloc[-1]), 6),
        "volume_average": (
            round(float(rolling_mean.iloc[-1]), 6)
            if not np.isnan(rolling_mean.iloc[-1])
            else 0.0
        ),
        "volume_ratio": (
            round(float(volume.iloc[-1] / rolling_mean.iloc[-1]), 6)
            if not np.isnan(rolling_mean.iloc[-1]) and rolling_mean.iloc[-1]
            else 0.0
        ),
    }


def calculate_pivot_points(frame: pd.DataFrame) -> dict[str, float]:
    last = frame.iloc[-2] if len(frame) > 1 else frame.iloc[-1]
    pivot = (float(last["high"]) + float(last["low"]) + float(last["close"])) / 3.0
    resistance1 = (2.0 * pivot) - float(last["low"])
    support1 = (2.0 * pivot) - float(last["high"])
    resistance2 = pivot + (float(last["high"]) - float(last["low"]))
    support2 = pivot - (float(last["high"]) - float(last["low"]))
    return {
        "pivot": round(pivot, 6),
        "r1": round(resistance1, 6),
        "s1": round(support1, 6),
        "r2": round(resistance2, 6),
        "s2": round(support2, 6),
    }


def calculate_support_resistance(
    frame: pd.DataFrame, lookback: int = 20
) -> dict[str, float]:
    recent = frame.tail(lookback)
    support = float(recent["low"].min())
    resistance = float(recent["high"].max())
    return {"support": round(support, 6), "resistance": round(resistance, 6)}


def calculate_fibonacci_retracement(frame: pd.DataFrame) -> dict[str, float]:
    swing_low = float(frame["low"].min())
    swing_high = float(frame["high"].max())
    diff = swing_high - swing_low
    levels = {
        "fib_0": swing_low,
        "fib_236": swing_high - diff * 0.236,
        "fib_382": swing_high - diff * 0.382,
        "fib_500": swing_high - diff * 0.5,
        "fib_618": swing_high - diff * 0.618,
        "fib_786": swing_high - diff * 0.786,
        "fib_1": swing_high,
    }
    return {key: round(float(value), 6) for key, value in levels.items()}


def calculate_fibonacci_extension(frame: pd.DataFrame) -> dict[str, float]:
    retracement = calculate_fibonacci_retracement(frame)
    swing_low = retracement["fib_0"]
    swing_high = retracement["fib_1"]
    diff = swing_high - swing_low
    return {
        "fib_ext_1272": round(swing_high + diff * 0.272, 6),
        "fib_ext_1618": round(swing_high + diff * 0.618, 6),
        "fib_ext_2000": round(swing_high + diff * 1.0, 6),
    }


def calculate_trendlines(frame: pd.DataFrame, lookback: int = 50) -> dict[str, float]:
    recent = frame.tail(lookback)
    x = np.arange(len(recent), dtype=float)
    close = recent["close"].astype(float).to_numpy()
    slope, intercept = np.polyfit(x, close, 1)
    projected = slope * (len(recent) - 1) + intercept
    return {
        "trend_slope": round(float(slope), 6),
        "trend_projection": round(float(projected), 6),
    }


def detect_market_structure(frame: pd.DataFrame, lookback: int = 20) -> dict[str, Any]:
    recent = frame.tail(lookback)
    latest_close = float(frame.iloc[-1]["close"])
    recent_high = float(recent["high"].max())
    recent_low = float(recent["low"].min())
    bias = (
        "bullish"
        if latest_close > recent_high * 0.995
        else "bearish" if latest_close < recent_low * 1.005 else "neutral"
    )
    return {
        "market_structure": bias,
        "recent_high": round(recent_high, 6),
        "recent_low": round(recent_low, 6),
    }


def detect_swings(frame: pd.DataFrame, order: int = 3) -> SwingPoints:
    highs = frame["high"].astype(float)
    lows = frame["low"].astype(float)
    swing_highs: list[dict[str, Any]] = []
    swing_lows: list[dict[str, Any]] = []
    for index in range(order, len(frame) - order):
        high_window = highs.iloc[index - order : index + order + 1]
        low_window = lows.iloc[index - order : index + order + 1]
        if highs.iloc[index] == high_window.max():
            swing_highs.append({"index": index, "price": float(highs.iloc[index])})
        if lows.iloc[index] == low_window.min():
            swing_lows.append({"index": index, "price": float(lows.iloc[index])})
    return SwingPoints(swing_highs=swing_highs, swing_lows=swing_lows)
