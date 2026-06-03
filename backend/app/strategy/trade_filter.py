from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CONFIDENCE_WEIGHTS = {
    "trend_alignment": 20,
    "market_structure": 20,
    "momentum": 15,
    "rsi": 10,
    "macd": 10,
    "session": 10,
    "news_risk": 5,
    "institutional_bias": 10,
}

MIN_RR = 1.5
SCALP_RR = 2.0
PREMIUM_RR = 3.0


@dataclass(slots=True)
class TradeFilterResult:
    symbol: str
    side: str
    approved: bool
    grade: str
    risk_level: str
    confidence_score: float
    quality_score: float
    risk_reward_ratio: float
    rr_category: str
    lot_size: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    news_risk: str
    institutional_approved: bool
    institutional_recommendation: str
    aggressive_recommendation: str
    aggressive_setup: dict[str, Any]
    estimated_probability: float
    reasons: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def allowed_to_alert(self) -> bool:
        return self.institutional_approved and self.grade in {"A+", "A"}

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["allowed_to_alert"] = self.allowed_to_alert
        return payload


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _unpack_confluence(confluence: Any) -> tuple[float, bool]:
    if hasattr(confluence, "get"):
        score = _safe_float(
            confluence.get("confidence_score", confluence.get("total", 0.0)), 0.0
        )
        passed = bool(confluence.get("passed", score >= 70.0))
        return score, passed
    score = _safe_float(
        getattr(confluence, "confidence_score", getattr(confluence, "total", 0.0))
    )
    passed = bool(getattr(confluence, "passed", score >= 70.0))
    return score, passed


def _trend_direction(trend: dict[str, Any]) -> str:
    value = str(trend.get("trend", "")).lower()
    if "bull" in value:
        return "bullish"
    if "bear" in value:
        return "bearish"
    return "sideways"


def _structure_direction(smc: dict[str, Any]) -> str:
    if smc.get("bos") and not smc.get("choch"):
        return "bullish"
    if smc.get("choch") and not smc.get("bos"):
        return "bearish"

    highs = [float(point["price"]) for point in smc.get("swing_highs", [])[-3:]]
    lows = [float(point["price"]) for point in smc.get("swing_lows", [])[-3:]]
    if len(highs) >= 2 and len(lows) >= 2:
        higher_highs = highs[-1] > highs[-2]
        higher_lows = lows[-1] > lows[-2]
        lower_highs = highs[-1] < highs[-2]
        lower_lows = lows[-1] < lows[-2]
        if higher_highs and higher_lows:
            return "bullish"
        if lower_highs and lower_lows:
            return "bearish"
    return "neutral"


def _speculative_direction(
    trend: dict[str, Any], smc: dict[str, Any], indicators: dict[str, Any]
) -> str:
    bullish = 0
    bearish = 0
    trend_dir = _trend_direction(trend)
    structure_dir = _structure_direction(smc)
    if trend_dir == "bullish":
        bullish += 2
    elif trend_dir == "bearish":
        bearish += 2
    if structure_dir == "bullish":
        bullish += 2
    elif structure_dir == "bearish":
        bearish += 2

    price = _safe_float(indicators.get("latest_close", indicators.get("close", 0.0)))
    ema20 = _safe_float(indicators.get("ema20", price), price)
    ema50 = _safe_float(indicators.get("ema50", price), price)
    rsi = _safe_float(indicators.get("rsi", 50.0), 50.0)
    histogram = _safe_float(indicators.get("histogram", 0.0), 0.0)
    macd = _safe_float(indicators.get("macd", 0.0), 0.0)
    signal = _safe_float(indicators.get("signal", 0.0), 0.0)

    bullish += 1 if rsi >= 50 else 0
    bearish += 1 if rsi < 50 else 0
    bullish += 1 if histogram > 0 or macd > signal else 0
    bearish += 1 if histogram < 0 or macd < signal else 0
    bullish += 1 if price > ema20 and price > ema50 else 0
    bearish += 1 if price < ema20 and price < ema50 else 0

    return "buy" if bullish >= bearish else "sell"


def _entry_near_level(
    entry: float, level: float, atr: float, tolerance: float = 0.75
) -> bool:
    return abs(entry - level) <= atr * tolerance


def _quality_warning_list(
    confidence_score: float,
    rr: float,
    trend_ok: bool,
    structure_ok: bool,
    news_risk: str,
) -> list[str]:
    warnings: list[str] = []
    if confidence_score < 70:
        warnings.append("Confidence below institutional threshold")
    if rr < MIN_RR:
        warnings.append("Risk Reward below minimum")
    if not trend_ok:
        warnings.append("Trend unclear")
    if not structure_ok:
        warnings.append("Structure conflict")
    if str(news_risk).lower() == "high":
        warnings.append("News risk high")
    return warnings


def _build_aggressive_setup(
    side: str,
    entry: float,
    stop_loss: float,
    support: float,
    resistance: float,
    atr: float,
    confidence_score: float,
    lot_size: float,
) -> dict[str, Any]:
    direction_sign = 1.0 if side == "buy" else -1.0
    if entry <= 0:
        entry = support if side == "buy" else resistance
    if stop_loss <= 0:
        stop_loss = entry - direction_sign * atr
    take_profit = entry + direction_sign * max(abs(entry - stop_loss) * 1.2, atr)
    take_profit_2 = entry + direction_sign * max(abs(entry - stop_loss) * 2.0, atr * 2)
    take_profit_3 = entry + direction_sign * max(abs(entry - stop_loss) * 3.0, atr * 3)
    rr = abs(take_profit - entry) / max(abs(entry - stop_loss), 1e-9)
    return {
        "direction": side.upper(),
        "entry": round(entry, 6),
        "stop_loss": round(stop_loss, 6),
        "take_profit": round(take_profit, 6),
        "take_profit_2": round(take_profit_2, 6),
        "take_profit_3": round(take_profit_3, 6),
        "risk_reward_ratio": round(rr, 2),
        "estimated_probability": round(max(0.0, min(confidence_score, 99.0)), 2),
        "lot_size": round(max(lot_size, 0.0), 4),
        "entry_zone": [round(entry - atr * 0.15, 6), round(entry + atr * 0.15, 6)],
        "setup_type": "Speculative",
    }


def _confidence_label(score: float) -> str:
    if score >= 90:
        return "Exceptional Setup"
    if score >= 80:
        return "A+"
    if score >= 70:
        return "A"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C"
    return "No Trade"


def _risk_level(score: float, rr: float) -> str:
    if rr < MIN_RR or score < 50:
        return "HIGH"
    if score < 60:
        return "HIGH"
    if score < 70:
        return "MEDIUM"
    if score < 80:
        return "LOW"
    if rr < SCALP_RR:
        return "MEDIUM"
    if rr < PREMIUM_RR:
        return "LOW"
    return "LOW"


def _rr_category(rr: float) -> str:
    if rr < MIN_RR:
        return "Reject"
    if rr < SCALP_RR:
        return "Scalping Only"
    if rr < PREMIUM_RR:
        return "Intraday Candidate"
    return "Premium Setup"


def evaluate_trade_candidate(
    symbol: str,
    indicators: dict[str, Any],
    trend: dict[str, Any],
    smc: dict[str, Any],
    session: dict[str, Any],
    confluence: Any,
    trade_setup: dict[str, Any],
    critic: dict[str, Any],
    news_risk: str = "low",
) -> TradeFilterResult:
    confluence_score, confluence_passed = _unpack_confluence(confluence)
    side = str(trade_setup.get("trade_side", "wait")).lower()
    if side not in {"buy", "sell"}:
        side = _speculative_direction(trend, smc, indicators)

    entry_price = _safe_float(trade_setup.get("entry_price", 0.0))
    stop_loss = _safe_float(trade_setup.get("stop_loss", 0.0))
    take_profit_1 = _safe_float(trade_setup.get("take_profit_1", 0.0))
    take_profit_2 = _safe_float(trade_setup.get("take_profit_2", 0.0))
    take_profit_3 = _safe_float(trade_setup.get("take_profit_3", 0.0))
    lot_size = _safe_float(trade_setup.get("lot_size", 0.0))
    raw_price = indicators.get("latest_close", indicators.get("close"))
    if raw_price is None:
        price = 0.0
    else:
        try:
            price = float(raw_price)
        except (ValueError, TypeError):
            price = 0.0
    atr = max(_safe_float(indicators.get("atr", 0.0)), 1e-9)
    support = _safe_float(smc.get("support", price), price)
    resistance = _safe_float(smc.get("resistance", price), price)
    rr = abs(take_profit_1 - entry_price) / max(abs(entry_price - stop_loss), 1e-9)

    buy = side == "buy"
    sell = side == "sell"
    trend_dir = _trend_direction(trend)
    structure_dir = _structure_direction(smc)

    ema20 = _safe_float(indicators.get("ema20", price), price)
    ema50 = _safe_float(indicators.get("ema50", price), price)
    ema200 = _safe_float(indicators.get("ema200", price), price)
    rsi = _safe_float(indicators.get("rsi", 50.0), 50.0)
    macd = _safe_float(indicators.get("macd", 0.0), 0.0)
    signal = _safe_float(indicators.get("signal", 0.0), 0.0)
    histogram = _safe_float(indicators.get("histogram", 0.0), 0.0)
    session_name = str(session.get("session", "")).lower()
    news = str(news_risk).lower()

    # Trend Validation
    # Bullish: Price > EMA20, Price > EMA50, Price > EMA200, RSI > 50, MACD Bullish
    # Bearish: Price < EMA20, Price < EMA50, Price < EMA200, RSI < 50, MACD Bearish
    bullish_components = [
        price > ema20,
        price > ema50,
        price > ema200,
        rsi > 50,
        macd > signal
    ]
    bearish_components = [
        price < ema20,
        price < ema50,
        price < ema200,
        rsi < 50,
        macd < signal
    ]
    all_bullish = all(bullish_components)
    all_bearish = all(bearish_components)
    trend_disagree = not all_bullish and not all_bearish

    trend_ok = all_bullish if buy else all_bearish if sell else False

    structure_ok = (structure_dir == "bullish") if buy else (structure_dir == "bearish")
    momentum_ok = (indicators.get("momentum", 0.0) > 0) if buy else (indicators.get("momentum", 0.0) < 0)
    rsi_ok = (rsi > 50) if buy else (rsi < 50)
    macd_ok = (macd > signal) if buy else (macd < signal)
    session_ok = session_name in {"london", "new_york", "overlap", "london_new_york"}
    news_ok = news != "high"
    institutional_bias_ok = bool(smc.get("institutional_footprint")) or structure_ok

    # Initial confidence based on weights
    confidence = 0.0
    confidence += CONFIDENCE_WEIGHTS["trend_alignment"] * (1.0 if trend_ok else 0.0)
    confidence += CONFIDENCE_WEIGHTS["market_structure"] * (1.0 if structure_ok else 0.0)
    confidence += CONFIDENCE_WEIGHTS["momentum"] * (1.0 if momentum_ok else 0.0)
    confidence += CONFIDENCE_WEIGHTS["rsi"] * (1.0 if rsi_ok else 0.0)
    confidence += CONFIDENCE_WEIGHTS["macd"] * (1.0 if macd_ok else 0.0)
    
    # Session contribution
    confidence += CONFIDENCE_WEIGHTS["session"] * (1.0 if session_ok else 0.5)
        
    confidence += CONFIDENCE_WEIGHTS["news_risk"] * (1.0 if news == "low" else 0.5 if news == "medium" else 0.0)
    confidence += CONFIDENCE_WEIGHTS["institutional_bias"] * (1.0 if institutional_bias_ok else 0.0)

    # Apply penalties / adjustments
    if trend_disagree:
        confidence -= 20
    if not structure_ok:
        confidence -= 20
    if (
        trend_dir != "sideways"
        and structure_dir != "neutral"
        and trend_dir != structure_dir
    ):
        confidence -= 20
    if lot_size <= 0:
        confidence -= 20
    if "asia" in session_name or "tokyo" in session_name or "sydney" in session_name:
        if "XAU" in symbol:
            confidence -= 15 # Weak Asian session for Gold trend trade

    # Volatility adjustment
    def _map_volatility(inds: dict[str, Any], prc: float) -> str:
        atr_val = float(inds.get("atr", 0.0))
        if prc <= 0:
            return "low"
        atr_pct = atr_val / prc
        if atr_pct >= 0.02:
            return "high"
        if atr_pct >= 0.005:
            return "medium"
        return "low"

    volatility_label = _map_volatility(indicators, price)
    if volatility_label == "low":
        confidence -= 10
    elif volatility_label == "high":
        confidence += 10

    confidence = max(0.0, min(100.0, round(confidence, 2)))
    quality_score = confidence

    # Trade grading
    def compute_grade(conf_score: float, rr_ratio: float) -> str:
        if conf_score >= 85 and rr_ratio >= 3.0:
            return "A+"
        elif conf_score >= 75 and rr_ratio >= 2.5:
            return "A"
        elif conf_score >= 65 and rr_ratio >= 2.0:
            return "B"
        elif conf_score >= 50 and rr_ratio >= 1.5:
            return "C"
        else:
            return "No Trade"

    grade = compute_grade(confidence, rr)
    risk_level = _risk_level(confidence, rr)
    rr_category = _rr_category(rr)

    # Rejection Reasons compilation (mandatory consistency rule)
    rejection_reasons: list[str] = []
    if confidence < 50:
        rejection_reasons.append(f"Confidence below threshold: {confidence}% (requires >= 50%)")
    if rr < 1.5:
        rejection_reasons.append(f"Risk Reward below minimum: 1:{rr:.2f} (requires >= 1.5)")
    if trend_disagree:
        rejection_reasons.append("Trend indicators disagree (Price, EMA, RSI, MACD not aligned)")
    elif not trend_ok:
        rejection_reasons.append("Trend not aligned with trade direction")
    if not structure_ok:
        rejection_reasons.append("Market structure not aligned with trade direction")
    if trend_dir != "sideways" and structure_dir != "neutral" and trend_dir != structure_dir:
        rejection_reasons.append("Trend and Structure conflict")
    if lot_size <= 0:
        rejection_reasons.append("Invalid lot size computed")
    if news == "high":
        rejection_reasons.append("High Impact News risk (CPI/NFP/FOMC/Interest Rates/Fed Speeches)")
    if not bool(critic.get("approved", False)):
        system_keywords = {"api", "http", "connection", "unauthorized", "exception", "error", "401", "404", "500", "status_code"}
        market_weaknesses = [
            w for w in critic.get("weaknesses", [])
            if not any(kw in w.lower() for kw in system_keywords)
        ]
        critic_rejection_text = "; ".join(market_weaknesses) or "Rejected by rule-based heuristic review"
        rejection_reasons.append(f"AI Critic rejection: {critic_rejection_text}")

    support_distance_ok = True
    resistance_distance_ok = True
    if buy:
        if resistance > entry_price:
            resistance_distance_ok = (resistance - entry_price) >= atr * 0.5
    else:
        if support < entry_price:
            support_distance_ok = (entry_price - support) >= atr * 0.5

    if not support_distance_ok or not resistance_distance_ok:
        if "Support and resistance too close to entry price" not in rejection_reasons:
            rejection_reasons.append("Support and resistance too close to entry price")

    # Critical Fix 2: Forbidden States Detection
    import math
    import logging
    logger = logging.getLogger(__name__)

    forbidden_state = False
    forbidden_reason = ""

    if price <= 0 or math.isnan(price):
        forbidden_state = True
        forbidden_reason = "Current Price is zero or negative"
    elif support > resistance:
        forbidden_state = True
        forbidden_reason = f"Support ({support}) is greater than Resistance ({resistance})"
    elif stop_loss == entry_price:
        forbidden_state = True
        forbidden_reason = "Stop Loss equals Entry Price"
    elif rr <= 0 or _safe_float(trade_setup.get("risk_reward_ratio", 0.0)) <= 0 or math.isnan(rr) or math.isnan(_safe_float(trade_setup.get("risk_reward_ratio", 0.0))):
        forbidden_state = True
        forbidden_reason = f"Risk Reward ratio is non-positive: {rr}"
    elif lot_size <= 0:
        forbidden_state = True
        forbidden_reason = f"Lot size is non-positive: {lot_size}"
    elif take_profit_1 == entry_price or take_profit_2 == entry_price or take_profit_3 == entry_price:
        forbidden_state = True
        forbidden_reason = "Target equals Entry Price"

    if forbidden_state:
        logger.warning(f"[Forbidden State Detected] Rejecting setup: {forbidden_reason}")
        approved = False
        institutional_approved = False
        if forbidden_reason not in rejection_reasons:
            rejection_reasons.append(forbidden_reason)
    else:
        approved = (grade != "No Trade") and (lot_size > 0) and (news != "high") and bool(critic.get("approved", False)) and support_distance_ok and resistance_distance_ok
        institutional_approved = approved and grade in {"A+", "A"}

    institutional_recommendation = side.upper() if institutional_approved else "NO TRADE"
    aggressive_recommendation = side.upper() if approved else "NO TRADE"
    aggressive_setup = _build_aggressive_setup(
        side=side,
        entry=entry_price,
        stop_loss=stop_loss,
        support=support,
        resistance=resistance,
        atr=atr,
        confidence_score=confidence,
        lot_size=lot_size,
    )

    reasons: list[str] = []
    if approved:
        if buy:
            if trend_ok:
                reasons.append("Strong bullish trend (Price > EMAs, RSI > 50, MACD Bullish)")
            if structure_ok:
                reasons.append("Bullish market structure (BOS / HH-HL)")
            if macd_ok:
                reasons.append("MACD histogram bullish")
            if rsi_ok:
                reasons.append("RSI momentum bullish (>50)")
            if institutional_bias_ok:
                reasons.append("Institutional footprint / bias bullish")
            if session_ok:
                reasons.append(f"Favorable trading session: {session_name.title()}")
        else:
            if trend_ok:
                reasons.append("Strong bearish trend (Price < EMAs, RSI < 50, MACD Bearish)")
            if structure_ok:
                reasons.append("Bearish market structure (BOS / LH-LL)")
            if macd_ok:
                reasons.append("MACD histogram bearish")
            if rsi_ok:
                reasons.append("RSI momentum bearish (<50)")
            if institutional_bias_ok:
                reasons.append("Institutional footprint / bias bearish")
            if session_ok:
                reasons.append(f"Favorable trading session: {session_name.title()}")

    warnings = rejection_reasons[:]
    if approved:
        warnings = ["Trade approved"]

    return TradeFilterResult(
        symbol=symbol,
        side=side,
        approved=approved,
        grade=grade,
        risk_level=risk_level,
        confidence_score=confidence,
        quality_score=quality_score,
        risk_reward_ratio=round(rr, 2),
        rr_category=rr_category,
        lot_size=round(lot_size, 4),
        entry_price=round(entry_price, 6),
        stop_loss=round(stop_loss, 6),
        take_profit_1=round(take_profit_1, 6),
        take_profit_2=round(take_profit_2, 6),
        take_profit_3=round(take_profit_3, 6),
        news_risk=news,
        institutional_approved=institutional_approved,
        institutional_recommendation=institutional_recommendation,
        aggressive_recommendation=aggressive_recommendation,
        aggressive_setup=aggressive_setup,
        estimated_probability=round(confidence, 2),
        reasons=reasons,
        rejection_reasons=rejection_reasons,
        warnings=warnings,
        checks={
            "trend_ok": trend_ok,
            "structure_ok": structure_ok,
            "momentum_ok": momentum_ok,
            "rsi_ok": rsi_ok,
            "macd_ok": macd_ok,
            "session_ok": session_ok,
            "news_ok": news_ok,
            "institutional_bias_ok": institutional_bias_ok,
        },
    )
