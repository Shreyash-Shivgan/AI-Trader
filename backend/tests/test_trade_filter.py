from app.strategy.trade_filter import evaluate_trade_candidate


def test_trade_filter_approves_strict_buy_setup():
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

    result = evaluate_trade_candidate(
        symbol="XAUUSD",
        indicators=indicators,
        trend=trend,
        smc=smc,
        session=session,
        confluence=confluence,
        trade_setup=trade_setup,
        critic=critic,
        news_risk="low",
    )

    assert result.approved is True
    assert result.grade == "A+"
    assert result.institutional_approved is True
    assert result.institutional_recommendation == "BUY"
    assert result.allowed_to_alert is True
    assert result.rejection_reasons == []
    assert result.aggressive_setup["direction"] == "BUY"


def test_trade_filter_flags_grade_c_aggressive_setup():
    indicators = {
        "atr": 1.8,
        "rsi": 52.0,
        "macd": 0.15,
        "signal": 0.1,
        "histogram": 0.05,
        "momentum": 1.0,
        "ema20": 99.5,
        "ema50": 99.0,
        "ema200": 98.5,
        "latest_close": 100.1,
        "volume_ratio": 1.0,
        "dxy_bias": 0.4,
    }
    trend = {"trend": "bullish"}
    smc = {
        "support": 99.0,
        "resistance": 102.0,
        "bos": False,
        "choch": False,
        "institutional_footprint": False,
        "market_structure": "neutral",
    }
    session = {"session": "london"}
    confluence = {"total": 55.0, "passed": False}
    trade_setup = {
        "trade_side": "buy",
        "entry_price": 100.2,
        "stop_loss": 99.2,
        "take_profit_1": 102.0,
        "take_profit_2": 102.4,
        "take_profit_3": 103.8,
        "lot_size": 0.03,
        "risk_reward_ratio": 1.8,
    }
    critic = {"approved": True}

    result = evaluate_trade_candidate(
        symbol="XAUUSD",
        indicators=indicators,
        trend=trend,
        smc=smc,
        session=session,
        confluence=confluence,
        trade_setup=trade_setup,
        critic=critic,
        news_risk="low",
    )

    assert result.grade == "C"
    assert result.approved is True
    assert result.institutional_approved is False
    assert result.institutional_recommendation == "NO TRADE"
    assert result.allowed_to_alert is False
    assert result.risk_level == "HIGH"
    assert result.aggressive_setup["direction"] in {"BUY", "SELL"}
    assert result.aggressive_setup["risk_reward_ratio"] >= 1.2
    assert result.warnings


def test_trade_filter_rejects_weak_setup_but_keeps_speculative_view():
    indicators = {
        "atr": 0.2,
        "rsi": 36.0,
        "macd": -0.3,
        "signal": 0.1,
        "histogram": -0.4,
        "ema20": 101.0,
        "ema50": 102.0,
        "latest_close": 100.0,
        "volume_ratio": 0.7,
        "dxy_bias": 0.2,
    }
    trend = {"trend": "sideways"}
    smc = {
        "support": 99.0,
        "resistance": 101.0,
        "bos": False,
        "choch": True,
        "institutional_footprint": False,
        "market_structure": "bearish",
    }
    session = {"session": "asian"}
    confluence = {"total": 31.0, "passed": False}
    trade_setup = {
        "trade_side": "buy",
        "entry_price": 100.0,
        "stop_loss": 99.8,
        "take_profit_1": 100.2,
        "take_profit_2": 100.3,
        "take_profit_3": 100.4,
        "lot_size": 0.0,
        "risk_reward_ratio": 1.0,
    }
    critic = {"approved": False}

    result = evaluate_trade_candidate(
        symbol="XAUUSD",
        indicators=indicators,
        trend=trend,
        smc=smc,
        session=session,
        confluence=confluence,
        trade_setup=trade_setup,
        critic=critic,
        news_risk="high",
    )

    assert result.approved is False
    assert result.grade == "No Trade"
    assert result.institutional_recommendation == "NO TRADE"
    assert result.allowed_to_alert is False
    assert result.aggressive_setup["direction"] in {"BUY", "SELL"}
    assert result.warnings
