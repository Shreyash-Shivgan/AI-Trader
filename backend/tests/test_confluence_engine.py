import pandas as pd

from app.services.confluence_engine import evaluate_confluence


def make_candle_frame(close_start: float = 1800.0, length: int = 100) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=length, freq="H")
    close = pd.Series([close_start + i * 0.1 for i in range(length)], index=idx)
    high = close + 1.0
    low = close - 1.0
    volume = pd.Series([1000 for _ in range(length)], index=idx)
    df = pd.DataFrame({"close": close, "high": high, "low": low, "volume": volume})
    return df


def test_evaluate_confluence_basic():
    df = make_candle_frame()
    indicators = {"atr": 2.0, "momentum": 1.0, "close": float(df.iloc[-1]["close"])}
    trend = {"trend": "bullish"}
    smc = {
        "support": float(df["low"].min()),
        "resistance": float(df["high"].max()),
        "institutional_footprint": True,
    }
    confluence = {"total": 80.0, "passed": True}
    setup = {
        "entry_zone": [
            float(df.iloc[-1]["close"]) - 0.5,
            float(df.iloc[-1]["close"]) + 0.5,
        ],
        "stop_loss": float(df.iloc[-1]["low"]),
        "take_profit_1": float(df.iloc[-1]["close"]) + 2.0,
        "take_profit_2": float(df.iloc[-1]["close"]) + 4.0,
        "take_profit_3": float(df.iloc[-1]["close"]) + 6.0,
        "risk_reward_ratio": 2.0,
        "trade_side": "buy",
    }
    critic = {"approved": True}

    result = evaluate_confluence(
        "XAUUSD", indicators, trend, smc, confluence, setup, critic
    )
    assert result["market_bias"] in {"bullish", "strong_bullish", "neutral"}
    assert isinstance(result["confidence_score"], float)
    assert "entry_zone" in result
    assert result["approved"] is True
