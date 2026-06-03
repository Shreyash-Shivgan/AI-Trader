from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=True)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value if value not in {"", None} else default


@dataclass(slots=True)
class Settings:
    app_name: str = _env("APP_NAME", "AI Trader") or "AI Trader"
    environment: str = _env("ENVIRONMENT", "development") or "development"
    log_level: str = _env("LOG_LEVEL", "INFO") or "INFO"

    database_url: str = (
        _env(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/ai_trader",
        )
        or "postgresql://postgres:postgres@localhost:5432/ai_trader"
    )
    redis_url: str = (
        _env("REDIS_URL", "redis://localhost:6379/0") or "redis://localhost:6379/0"
    )

    twelvedata_api_key: str | None = _env("TWELVEDATA_API_KEY")
    openai_api_key: str | None = _env("OPENAI_API_KEY")
    telegram_bot_token: str | None = _env("TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = _env("TELEGRAM_CHAT_ID")

    llm_provider: str = _env("LLM_PROVIDER", "openai") or "openai"
    openai_model: str = _env("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
    gemini_model: str = _env("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"

    default_symbols: list[str] = field(
        default_factory=lambda: ["XAU/USD", "EUR/USD", "GBP/USD", "USD/JPY"]
    )
    monitored_timeframes: list[str] = field(
        default_factory=lambda: ["1m", "5m", "15m", "30m", "1h", "4h", "1day"]
    )
    confidence_threshold: float = float(_env("CONFIDENCE_THRESHOLD", "70") or 70)
    risk_per_trade_percent: float = float(_env("RISK_PER_TRADE_PERCENT", "1.0") or 1.0)
    scheduler_enabled: bool = (
        _env("SCHEDULER_ENABLED", "true") or "true"
    ).lower() == "true"
    telegram_enabled: bool = (
        _env("TELEGRAM_ENABLED", "true") or "true"
    ).lower() == "true"
    timezone: str = _env("APP_TIMEZONE", "UTC") or "UTC"

    def as_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "environment": self.environment,
            "log_level": self.log_level,
            "database_url": self.database_url,
            "redis_url": self.redis_url,
            "default_symbols": self.default_symbols,
            "monitored_timeframes": self.monitored_timeframes,
            "confidence_threshold": self.confidence_threshold,
            "risk_per_trade_percent": self.risk_per_trade_percent,
            "scheduler_enabled": self.scheduler_enabled,
            "telegram_enabled": self.telegram_enabled,
            "timezone": self.timezone,
            "llm_provider": self.llm_provider,
            "openai_model": self.openai_model,
            "gemini_model": self.gemini_model,
        }


settings = Settings()
