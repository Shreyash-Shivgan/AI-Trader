from __future__ import annotations

import os
from typing import Any

import httpx

from app.config import settings


class CriticDecisionError(RuntimeError):
    pass


async def critic_review(
    trade_setup: dict[str, Any],
    analysis_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Support legacy OPENAI_API_KEY env or explicit GEMINI_API_KEY
    api_key = (
        settings.openai_api_key
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )

    # Allow caller to select LLM provider via env var. Defaults to 'openai'.
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    # Auto-detect if key is a Gemini API key
    if api_key and provider == "openai":
        if api_key.startswith("AIzaSy") or api_key.startswith("AQ."):
            provider = "gemini"

    analysis_context = analysis_context or {}

    def _heuristic_review() -> dict[str, Any]:
        score = float(trade_setup.get("confidence_score", 0.0))
        rr = float(trade_setup.get("risk_reward_ratio", 0.0) or 0.0)
        price = float(
            analysis_context.get("price", trade_setup.get("entry_price", 0.0)) or 0.0
        )
        entry = float(trade_setup.get("entry_price", 0.0) or 0.0)
        stop = float(trade_setup.get("stop_loss", 0.0) or 0.0)
        support = float(analysis_context.get("support", 0.0) or 0.0)
        resistance = float(analysis_context.get("resistance", 0.0) or 0.0)
        atr = float(analysis_context.get("atr", 0.0) or 0.0)
        trade_side = str(
            analysis_context.get("trade_side", trade_setup.get("trade_side", ""))
        ).lower()
        trend_direction = str(
            analysis_context.get("trend_direction", "sideways")
        ).lower()
        structure_direction = str(
            analysis_context.get("structure_direction", "neutral")
        ).lower()
        trend_ok = (trade_side == "buy" and trend_direction == "bullish") or (
            trade_side == "sell" and trend_direction == "bearish"
        )
        structure_ok = (trade_side == "buy" and structure_direction == "bullish") or (
            trade_side == "sell" and structure_direction == "bearish"
        )
        volatility_ok = atr > 0 and price > 0 and (atr / price) >= 0.001
        
        support_distance_ok = True
        resistance_distance_ok = True
        if trade_side == "buy":
            if resistance > entry:
                resistance_distance_ok = (resistance - entry) >= atr * 0.5
        elif trade_side == "sell":
            if support < entry:
                support_distance_ok = (entry - support) >= atr * 0.5

        major_contradiction = (
            not trend_ok
            or not structure_ok
            or not volatility_ok
            or not support_distance_ok
            or not resistance_distance_ok
            or rr < 1.5
        )

        approved = score >= 50 and not major_contradiction
        weaknesses: list[str] = []
        if rr < 1.5:
            weaknesses.append("Risk Reward below minimum")
        if not trend_ok:
            weaknesses.append("Trend unclear")
        if not structure_ok:
            weaknesses.append("Structure conflict")
        if not volatility_ok:
            weaknesses.append("Volatility is too low")
        if not support_distance_ok or not resistance_distance_ok:
            weaknesses.append("Support and resistance too close")
        if score < 50:
            weaknesses.append("Confidence below threshold")
        review = "APPROVED" if approved else "REJECTED"
        if weaknesses:
            review += ": " + "; ".join(weaknesses)
        return {"approved": approved, "weaknesses": weaknesses, "review": review}

    if not api_key:
        return _heuristic_review() | {"unavailable": True}

    prompt_system = (
        "You are the AI Trading Auditor and Critic. Your goal is to attempt to invalidate every trade setup.\n"
        "Ask: Why can this trade fail?\n"
        "Check and list every weakness relating to:\n"
        "- Trend Conflict\n"
        "- Structure Conflict\n"
        "- Low Volume\n"
        "- Low Volatility\n"
        "- Nearby Support\n"
        "- Nearby Resistance\n"
        "- Poor RR (Must be >= 1.5)\n"
        "- Upcoming News\n"
        "- Weak Momentum\n\n"
        "If any major contradiction or weakness exists, you must reject the trade.\n"
        "Return a short JSON with fields: approved (true/false), weaknesses (list of strings), rationale (string)."
    )
    prompt_user = (
        "Review this trade setup and return JSON with approved (true/false), weaknesses (list), and rationale.\n"
        f"Trade setup: {trade_setup}\n"
        f"Analysis context: {analysis_context}"
    )
    full_prompt = prompt_system + "\n\n" + prompt_user

    import json

    if provider == "openai":
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=api_key)
            response = await client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                input=[
                    {"role": "system", "content": prompt_system},
                    {"role": "user", "content": prompt_user},
                ],
            )
            text = response.output_text or ""
            try:
                # Find JSON block or parse direct
                clean_text = text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                parsed = json.loads(clean_text)
                return {
                    "approved": bool(parsed.get("approved", False)),
                    "review": parsed.get("rationale", text),
                    "weaknesses": parsed.get("weaknesses", []),
                }
            except Exception:
                approved = '"approved": true' in text.lower()
                return {
                    "approved": approved,
                    "review": text,
                    "weaknesses": [],
                }
        except Exception as exc:  # fallback to heuristic on LLM failure
            return _heuristic_review() | {"weaknesses": [str(exc)], "unavailable": True}

    if provider == "gemini":
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Determine URL and payload depending on legacy text-bison vs modern Gemini models
        if "bison" in model:
            url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generate?key={api_key}"
            payload = {"prompt": {"text": full_prompt}, "temperature": 0.0}
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": full_prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.0,
                    "responseMimeType": "application/json"
                }
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            
            # Extract generated response text
            candidates = data.get("candidates") or []
            text = ""
            if candidates:
                content_obj = candidates[0].get("content") or {}
                parts = content_obj.get("parts") or []
                if parts:
                    text = parts[0].get("text", "")
                else:
                    text = candidates[0].get("output", "") or candidates[0].get("content", "")

            try:
                # Find JSON block or parse direct
                clean_text = text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                parsed = json.loads(clean_text)
                return {
                    "approved": bool(parsed.get("approved", False)),
                    "review": parsed.get("rationale", text),
                    "weaknesses": parsed.get("weaknesses", []),
                }
            except Exception:
                approved = '"approved": true' in text.lower()
                return {
                    "approved": approved,
                    "review": text,
                    "weaknesses": [],
                }
        except Exception as exc:
            return _heuristic_review() | {"weaknesses": [str(exc)], "unavailable": True}

    # Unknown provider -> heuristic fallback
    return _heuristic_review() | {"weaknesses": [f"unknown provider {provider}"], "unavailable": True}
