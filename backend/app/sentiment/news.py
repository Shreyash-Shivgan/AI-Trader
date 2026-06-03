from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

import httpx


@dataclass(slots=True)
class NewsEvent:
    source: str
    title: str
    url: str | None
    published_at: datetime | None
    impact: str
    sentiment: str
    symbol: str | None = None
    raw_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.published_at is not None:
            payload["published_at"] = self.published_at.isoformat()
        return payload


class NewsIntelligenceEngine:
    def __init__(self, sources: list[str] | None = None) -> None:
        self.sources = sources or []

    async def fetch_rss(self, source_url: str, source_name: str) -> list[NewsEvent]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(source_url)
            response.raise_for_status()
            content = response.text
        items: list[NewsEvent] = []
        for line in content.splitlines():
            if "<title>" in line and "</title>" in line:
                title = line.replace("<title>", "").replace("</title>", "").strip()
                if title.lower() in {source_name.lower(), "rss", "channel"}:
                    continue
                sentiment = self.classify_text(title)
                items.append(
                    NewsEvent(
                        source=source_name,
                        title=title,
                        url=None,
                        published_at=datetime.now(timezone.utc),
                        impact="medium",
                        sentiment=sentiment,
                    )
                )
        return items

    @staticmethod
    def classify_text(text: str) -> str:
        lowered = text.lower()
        bullish_terms = [
            "rate cut",
            "dovish",
            "weak dollar",
            "slowdown",
            "cooling inflation",
        ]
        bearish_terms = [
            "rate hike",
            "hawkish",
            "hot inflation",
            "strong dollar",
            "risk-off",
        ]
        if any(term in lowered for term in bullish_terms):
            return "bullish"
        if any(term in lowered for term in bearish_terms):
            return "bearish"
        return "neutral"

    def classify_impact(self, text: str) -> str:
        lowered = text.lower()
        if any(
            term in lowered for term in ["fomc", "cpi", "ppi", "nfp", "gdp", "rates"]
        ):
            return "high"
        return "medium"
