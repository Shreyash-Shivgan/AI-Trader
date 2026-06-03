import math
import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock
from app.strategy.trade_filter import evaluate_trade_candidate
from app.services.analysis_engine import AnalysisEngine
from app.services.market_data import MarketDataError


# Setup basic valid helper data
def get_base_inputs():
    indicators = {
        "atr": 2.0,
        "rsi": 58.0,
        "macd": 1.2,
        "signal": 0.8,
        "histogram": 0.4,
        "ema20": 97.0,
        "ema50": 96.0,
        "ema200": 95.0,
        "latest_close": 100.0,
        "volume_ratio": 1.4,
        "dxy_bias": 0.8,
    }
    trend = {"trend": "strong_bullish"}
    smc = {
        "support": 98.0,
        "resistance": 106.0,
        "bos": True,
        "choch": False,
        "institutional_footprint": True,
        "market_structure": "bullish",
    }
    session = {"session": "london"}
    confluence = {"total": 82.0, "passed": True}
    trade_setup = {
        "trade_side": "buy",
        "entry_price": 98.5,
        "stop_loss": 96.5,
        "take_profit_1": 106.5,
        "take_profit_2": 110.0,
        "take_profit_3": 114.0,
        "lot_size": 0.05,
        "risk_reward_ratio": 4.0,
    }
    critic = {"approved": True}
    return indicators, trend, smc, session, confluence, trade_setup, critic


def test_current_price_zero():
    indicators, trend, smc, session, confluence, trade_setup, critic = get_base_inputs()
    indicators["latest_close"] = 0.0
    result = evaluate_trade_candidate(
        symbol="XAUUSD",
        indicators=indicators,
        trend=trend,
        smc=smc,
        session=session,
        confluence=confluence,
        trade_setup=trade_setup,
        critic=critic,
    )
    assert result.approved is False
    assert any("Current Price is zero or negative" in reason or "Invalid current market price" in reason for reason in result.rejection_reasons)


def test_current_price_none():
    indicators, trend, smc, session, confluence, trade_setup, critic = get_base_inputs()
    indicators["latest_close"] = None
    result = evaluate_trade_candidate(
        symbol="XAUUSD",
        indicators=indicators,
        trend=trend,
        smc=smc,
        session=session,
        confluence=confluence,
        trade_setup=trade_setup,
        critic=critic,
    )
    assert result.approved is False
    assert any("Current Price is zero or negative" in reason or "Invalid current market price" in reason for reason in result.rejection_reasons)


def test_current_price_nan():
    indicators, trend, smc, session, confluence, trade_setup, critic = get_base_inputs()
    indicators["latest_close"] = float("nan")
    result = evaluate_trade_candidate(
        symbol="XAUUSD",
        indicators=indicators,
        trend=trend,
        smc=smc,
        session=session,
        confluence=confluence,
        trade_setup=trade_setup,
        critic=critic,
    )
    assert result.approved is False
    assert any("Current Price is zero or negative" in reason or "Invalid current market price" in reason for reason in result.rejection_reasons)


def test_lot_size_zero_or_negative():
    indicators, trend, smc, session, confluence, trade_setup, critic = get_base_inputs()
    trade_setup["lot_size"] = 0.0
    result = evaluate_trade_candidate(
        symbol="XAUUSD",
        indicators=indicators,
        trend=trend,
        smc=smc,
        session=session,
        confluence=confluence,
        trade_setup=trade_setup,
        critic=critic,
    )
    assert result.approved is False
    assert any("Lot size is non-positive" in reason or "Invalid lot size" in reason for reason in result.rejection_reasons)


def test_support_greater_than_resistance():
    indicators, trend, smc, session, confluence, trade_setup, critic = get_base_inputs()
    smc["support"] = 110.0
    smc["resistance"] = 100.0
    result = evaluate_trade_candidate(
        symbol="XAUUSD",
        indicators=indicators,
        trend=trend,
        smc=smc,
        session=session,
        confluence=confluence,
        trade_setup=trade_setup,
        critic=critic,
    )
    assert result.approved is False
    assert any("is greater than Resistance" in reason for reason in result.rejection_reasons)


def test_invalid_risk_reward():
    indicators, trend, smc, session, confluence, trade_setup, critic = get_base_inputs()
    trade_setup["risk_reward_ratio"] = -1.5
    result = evaluate_trade_candidate(
        symbol="XAUUSD",
        indicators=indicators,
        trend=trend,
        smc=smc,
        session=session,
        confluence=confluence,
        trade_setup=trade_setup,
        critic=critic,
    )
    assert result.approved is False
    assert any("Risk Reward ratio is non-positive" in reason for reason in result.rejection_reasons)


def test_approved_trade_formatting():
    from app.telegram_bot import format_price
    # Test price formatting output
    price = 4512.40
    entry = 4511.50
    stop = 4503.50
    tp1 = 4525.0
    tp2 = 4535.0
    tp3 = 4550.0

    assert format_price(price) == "4512.40"
    assert format_price(entry) == "4511.50"
    assert format_price(stop) == "4503.50"
    assert format_price(tp1) == "4525"
    assert format_price(tp2) == "4535"
    assert format_price(tp3) == "4550"

    # Verify classification logic for setups
    def get_classification(rr):
        if rr <= 1.8:
            return "SCALP"
        elif rr <= 3.0:
            return "INTRADAY"
        else:
            return "SWING"
    assert get_classification(1.5) == "SCALP"
    assert get_classification(1.8) == "SCALP"
    assert get_classification(2.5) == "INTRADAY"
    assert get_classification(3.0) == "INTRADAY"
    assert get_classification(3.5) == "SWING"


def test_no_trade_formatting():
    # Verify price formatting rules on boundaries
    support = 4456.92
    resistance = 4474.10
    from app.telegram_bot import format_price
    assert format_price(support) == "4456.92"
    assert format_price(resistance) == "4474.10"


def test_analysis_engine_raises_value_error_on_invalid_price():
    import asyncio
    db_mock = MagicMock()
    md_service_mock = MagicMock()
    
    df = pd.DataFrame([{"close": 0.0, "high": 0.0, "low": 0.0, "volume": 100, "datetime": "2023-01-01"}])
    df["datetime"] = pd.to_datetime(df["datetime"])
    
    md_service_mock.get_dataframe = AsyncMock(return_value=df)
    
    engine = AnalysisEngine(db=db_mock, market_data_service=md_service_mock)
    with pytest.raises(ValueError, match="Invalid current market price received"):
        asyncio.run(engine.analyze_symbol("XAUUSD", "5m"))


def test_new_telegram_signal_formatting():
    from app.utils.formatting import generate_telegram_message
    
    # 1. Test SELL LIMIT (Limit Order format)
    # entry = 4474.10, current = 4455.50, atr = 1.5, direction = SELL
    # entry - current = 18.6 > atr * 0.15 = 0.225 -> Limit Order
    msg_limit = generate_telegram_message(
        symbol="XAUUSD",
        current_price=4455.50,
        entry_price=4474.10,
        direction="SELL",
        stop_loss=4479.29,
        tp1=4465,
        tp2=4455,
        tp3=4440,
        rr=3.6,
        lot_size=0.01,
        grade="B",  # Medium strength
        atr=1.5,
        support=4456.92,
        resistance=4474.10
    )
    
    lines_limit = msg_limit.splitlines()
    assert lines_limit[0] == "🚨 XAUUSD | SELL LIMIT"
    assert "Price: 4455.50" in lines_limit
    assert "Entry: 4474.10" in lines_limit
    assert "SL: 4479.29" in lines_limit
    assert "TP1: 4465" in lines_limit
    assert "TP2: 4455" in lines_limit
    assert "TP3: 4440" in lines_limit
    assert "RR: 1:3.6 | Lot: 0.01" in lines_limit
    assert "Strength: Medium" in lines_limit
    assert "Action: Wait for Entry" in lines_limit
    
    # 2. Test SELL NOW (Market Order format, within 0.15 * atr)
    # entry = 4455.50, current = 4455.50
    msg_market = generate_telegram_message(
        symbol="XAUUSD",
        current_price=4455.50,
        entry_price=4455.50,
        direction="SELL",
        stop_loss=4462.00,
        tp1=4448,
        tp2=4440,
        tp3=4430,
        rr=2.8,
        lot_size=0.01,
        grade="A",  # Strong strength
        atr=1.5,
        support=4456.92,
        resistance=4474.10
    )
    lines_market = msg_market.splitlines()
    assert lines_market[0] == "🚨 XAUUSD | SELL NOW"
    assert "Price: 4455.50" in lines_market
    assert not any(l.startswith("Entry:") for l in lines_market)
    assert "SL: 4462" in lines_market
    assert "TP1: 4448" in lines_market
    assert "TP2: 4440" in lines_market
    assert "TP3: 4430" in lines_market
    assert "RR: 1:2.8 | Lot: 0.01" in lines_market
    assert "Strength: Strong" in lines_market
    assert "Action: Enter Now" in lines_market

    # 3. Test Speculative (No Quality Setup format)
    msg_spec = generate_telegram_message(
        symbol="XAUUSD",
        current_price=4455.50,
        entry_price=4474.10,
        direction="SELL",
        stop_loss=4479.29,
        tp1=4465,
        tp2=4455,
        tp3=4440,
        rr=3.6,
        lot_size=0.01,
        grade="Speculative",
        atr=1.5,
        support=4456.92,
        resistance=4474.10
    )
    lines_spec = msg_spec.splitlines()
    assert lines_spec[0] == "⚠️ XAUUSD"
    assert "Price: 4455.50" in lines_spec
    assert "Buy Above: 4474.10" in lines_spec
    assert "Sell Below: 4456.92" in lines_spec
    assert "Expected: Bearish" in lines_spec
    assert "Action: Wait" in lines_spec

