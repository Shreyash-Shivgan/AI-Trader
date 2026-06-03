from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

DEFAULT_WEIGHTS = {
    "trend_alignment": 20,
    "market_structure": 20,
    "momentum": 15,
    "rsi": 10,
    "macd": 10,
    "session": 10,
    "news_risk": 5,
    "institutional_bias": 10,
}


@dataclass(slots=True)
class ConfluenceScore:
    total: float
    threshold: float
    components: dict[str, float]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["confidence_score"] = round(self.total, 2)
        return payload


def score_confluence(
    components: dict[str, float], threshold: float = 70.0
) -> ConfluenceScore:
    total = 0.0
    for factor, weight in DEFAULT_WEIGHTS.items():
        component_score = max(0.0, min(1.0, float(components.get(factor, 0.0))))
        total += weight * component_score
    return ConfluenceScore(
        total=round(total, 2),
        threshold=threshold,
        components=components,
        passed=total >= threshold,
    )
