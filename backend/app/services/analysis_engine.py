from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.indicators.advanced import (
    calculate_adx,
    calculate_bollinger_bands,
    calculate_cci,
    calculate_fibonacci_extension,
    calculate_fibonacci_retracement,
    calculate_ichimoku,
    calculate_momentum,
    calculate_obv,
    calculate_pivot_points,
    calculate_roc,
    calculate_stochastic_rsi,
    calculate_support_resistance,
    calculate_trendlines,
    calculate_vwap,
    calculate_volume_analysis,
    detect_market_structure,
)
from app.indicators.atr import calculate_atr
from app.indicators.ema import calculate_ema
from app.indicators.macd import calculate_macd
from app.indicators.rsi import calculate_rsi
from app.risks.manager import RiskManager
from app.scoring.confluence import score_confluence
from app.sentiment.news import NewsIntelligenceEngine
from app.services.market_data import MarketDataService
from app.strategy.critic import critic_review
from app.strategy.correlation import correlation_snapshot
from app.strategy.session import session_bias
from app.strategy.setup_generator import generate_trade_setup
from app.strategy.smart_money import detect_smart_money_concepts
from app.strategy.trend import detect_trend
from app.strategy.trade_filter import evaluate_trade_candidate
from app.services.confluence_engine import evaluate_confluence


class AnalysisEngine:
    def __init__(self, db: Session, market_data_service: MarketDataService) -> None:
        self.db = db
        self.market_data_service = market_data_service
        self.news_engine = NewsIntelligenceEngine()

    async def analyze_symbol(
        self,
        symbol: str,
        timeframe: str = "5m",
        account_balance: float = 10000.0,
        risk_percent: float = 1.0,
    ) -> dict[str, Any]:
        candles = await self.market_data_service.get_dataframe(symbol, timeframe, 200)
        
        if candles.empty:
            raise MarketDataError("No market data returned (candles empty)")
            
        import math
        import logging
        logger = logging.getLogger(__name__)

        latest_close_val = candles.iloc[-1]["close"]
        if latest_close_val is None:
            raise ValueError("Current market price missing")
        try:
            current_price = float(latest_close_val)
        except (ValueError, TypeError):
            raise ValueError("Invalid current market price received")
        if current_price <= 0:
            raise ValueError("Invalid current market price received")
        if math.isnan(current_price):
            raise ValueError("Current market price is NaN")

        # Explicitly overwrite the close column of the last candle to be 100% sure it's the validated price
        candles.loc[candles.index[-1], "close"] = current_price

        basic_indicators = {
            **calculate_ema(candles),
            "rsi": calculate_rsi(candles),
            **calculate_macd(candles),
            "atr": calculate_atr(candles),
            **calculate_bollinger_bands(candles),
            "vwap": calculate_vwap(candles),
            **calculate_adx(candles),
            **calculate_stochastic_rsi(candles),
            **calculate_ichimoku(candles),
            "cci": calculate_cci(candles),
            "momentum": calculate_momentum(candles),
            "roc": calculate_roc(candles),
            "obv": calculate_obv(candles),
            **calculate_volume_analysis(candles),
            **calculate_pivot_points(candles),
            **calculate_support_resistance(candles),
            **calculate_fibonacci_retracement(candles),
            **calculate_fibonacci_extension(candles),
            **calculate_trendlines(candles),
            **detect_market_structure(candles),
            "latest_close": current_price,
        }
        trend = detect_trend(
            candles.assign(
                **{
                    k: v
                    for k, v in basic_indicators.items()
                    if k in {"ema20", "ema50", "ema200"}
                }
            )
        )
        session = session_bias()
        smc = detect_smart_money_concepts(candles)
        risk = RiskManager().calculate(
            account_balance,
            risk_percent,
            basic_indicators["atr"],
            basic_indicators["atr"] * 2,
            current_price,
        )
        price = current_price
        ema20 = float(basic_indicators.get("ema20", price))
        ema50 = float(basic_indicators.get("ema50", price))
        ema200 = float(basic_indicators.get("ema200", price))
        rsi = float(basic_indicators.get("rsi", 50.0))
        macd = float(basic_indicators.get("macd", 0.0))
        signal = float(basic_indicators.get("signal", 0.0))
        momentum_val = float(basic_indicators.get("momentum", 0.0))
        is_bullish = trend["trend"] in {"bullish", "strong_bullish"}

        # Calculate structure direction
        highs = [float(point["price"]) for point in smc.get("swing_highs", [])[-3:]]
        lows = [float(point["price"]) for point in smc.get("swing_lows", [])[-3:]]
        higher_highs = highs[-1] > highs[-2] if len(highs) >= 2 else False
        higher_lows = lows[-1] > lows[-2] if len(lows) >= 2 else False
        lower_highs = highs[-1] < highs[-2] if len(highs) >= 2 else False
        lower_lows = lows[-1] < lows[-2] if len(lows) >= 2 else False
        bullish_bos = bool(smc.get("bos"))
        bearish_bos = bool(smc.get("choch"))

        structure_dir = "neutral"
        if bullish_bos or (higher_highs and higher_lows):
            structure_dir = "bullish"
        elif bearish_bos or (lower_highs and lower_lows):
            structure_dir = "bearish"

        if is_bullish:
            trend_align = 1.0 if (price > ema20 and price > ema50 and price > ema200 and macd > signal and rsi > 50) else 0.0
            struct_align = 1.0 if structure_dir == "bullish" else 0.0
            mom_align = 1.0 if momentum_val > 0 else 0.0
            rsi_align = 1.0 if rsi > 50 else 0.0
            macd_align = 1.0 if macd > signal else 0.0
            inst_bias = 1.0 if smc.get("institutional_footprint") or structure_dir == "bullish" else 0.0
        else:
            trend_align = 1.0 if (price < ema20 and price < ema50 and price < ema200 and macd < signal and rsi < 50) else 0.0
            struct_align = 1.0 if structure_dir == "bearish" else 0.0
            mom_align = 1.0 if momentum_val < 0 else 0.0
            rsi_align = 1.0 if rsi < 50 else 0.0
            macd_align = 1.0 if macd < signal else 0.0
            inst_bias = 1.0 if smc.get("institutional_footprint") or structure_dir == "bearish" else 0.0

        confluence = score_confluence(
            {
                "trend_alignment": trend_align,
                "market_structure": struct_align,
                "momentum": mom_align,
                "rsi": rsi_align,
                "macd": macd_align,
                "session": 1.0 if session["session"] in {"london", "new_york"} else 0.5,
                "news_risk": 1.0,  # default placeholder, evaluated dynamically in filter
                "institutional_bias": inst_bias,
            },
            threshold=50.0,
        )
        setup = generate_trade_setup(
            candles,
            direction=(
                "bullish"
                if trend["trend"] in {"bullish", "strong_bullish"}
                else "bearish"
            ),
            confidence_score=confluence.total,
            account_balance=account_balance,
            risk_percent=risk_percent,
        )
        critic = await critic_review(
            setup,
            analysis_context={
                "price": current_price,
                "atr": basic_indicators["atr"],
                "support": smc.get("support"),
                "resistance": smc.get("resistance"),
                "trade_side": setup.get("trade_side"),
                "trend_direction": (
                    "bullish"
                    if trend.get("trend") in {"bullish", "strong_bullish"}
                    else (
                        "bearish"
                        if trend.get("trend") in {"bearish", "strong_bearish"}
                        else "sideways"
                    )
                ),
                "structure_direction": (
                    "bullish"
                    if smc.get("bos") and not smc.get("choch")
                    else (
                        "bearish"
                        if smc.get("choch") and not smc.get("bos")
                        else "neutral"
                    )
                ),
            },
        )
        trade_review = evaluate_trade_candidate(
            symbol=symbol,
            indicators={
                **basic_indicators,
                "latest_close": current_price,
            },
            trend=trend,
            smc=smc,
            session=session,
            confluence=confluence,
            trade_setup=setup,
            critic=critic,
            news_risk="low",
        )
        confluence_map = evaluate_confluence(
            symbol=symbol,
            indicators={
                **basic_indicators,
                "latest_close": current_price,
            },
            trend=trend,
            smc=smc,
            confluence=confluence,
            trade_setup=setup,
            critic=critic,
            trade_review=trade_review.to_dict(),
            session=session,
        )

        logger.info(
            f"[INTERNAL LOG] Symbol={symbol} | Current Price={current_price} | "
            f"Support={smc.get('support')} | Resistance={smc.get('resistance')} | "
            f"ATR={basic_indicators.get('atr')} | RR={setup.get('risk_reward_ratio')} | "
            f"Lot Size={setup.get('lot_size')} | Entry={setup.get('entry_price')} | "
            f"Stop={setup.get('stop_loss')} | Targets={{"
            f"TP1: {setup.get('take_profit_1')}, TP2: {setup.get('take_profit_2')}, TP3: {setup.get('take_profit_3')}}}"
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": basic_indicators,
            "trend": trend,
            "session": session,
            "smart_money": smc,
            "risk": risk.to_dict(),
            "confluence": confluence.to_dict(),
            "trade_setup": setup,
            "trade_review": trade_review.to_dict(),
            "critic": critic,
            "approved": trade_review.approved,
            "confluence_map": confluence_map,
        }
