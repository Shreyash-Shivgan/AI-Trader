from __future__ import annotations

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def candles_to_df(data: dict | list[dict]) -> pd.DataFrame:
    values = data.get("values", []) if isinstance(data, dict) else data
    frame = pd.DataFrame(values)
    if frame.empty:
        logger.info("[DataFrame Builder] candles_to_df: empty frame constructed")
        return frame

    if "datetime" in frame.columns:
        frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True, errors="coerce")
        frame = frame.dropna(subset=["datetime"])

    for column in ("open", "high", "low", "close", "volume"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if "datetime" in frame.columns:
        frame = frame.sort_values("datetime")
        
    logger.info(
        f"[DataFrame Builder] candles_to_df: shape={frame.shape}, "
        f"Latest Close={frame.iloc[-1]['close'] if 'close' in frame.columns else 'N/A'}"
    )
    return frame.reset_index(drop=True)
