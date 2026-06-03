from __future__ import annotations

from typing import Any, Dict, Tuple

import pandas as pd


def _build_close_dataframe(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return a DataFrame of aligned close prices for provided frames.

    The function extracts the `close` column from each frame, coerces to numeric,
    and aligns by index using an inner join so correlations are computed on
    synchronous observations.
    """
    series_map: dict[str, pd.Series] = {}
    for symbol, frame in frames.items():
        if frame is None or frame.empty:
            continue
        if "close" not in frame.columns:
            continue
        s = pd.to_numeric(frame["close"], errors="coerce")
        # preserve the index (usually datetime) when present
        s = s.rename(symbol)
        series_map[symbol] = s

    if len(series_map) < 2:
        return pd.DataFrame()

    df = pd.concat(series_map.values(), axis=1, join="inner")
    return df


def compute_pairwise_correlations(
    frames: dict[str, pd.DataFrame], method: str = "pearson", min_periods: int = 30
) -> Dict[str, Any]:
    """Compute a pairwise correlation matrix for the `close` series in `frames`.

    Returns a JSON-serializable dict with the matrix and metadata.
    """
    df = _build_close_dataframe(frames)
    if df.empty or df.shape[1] < 2:
        return {"correlations": {}, "summary": "insufficient_data"}

    matrix = df.corr(method=method).fillna(0.0)
    return {"correlations": matrix.round(4).to_dict(), "summary": "computed"}


def rolling_correlation_summary(
    frames: dict[str, pd.DataFrame], window: int = 50
) -> Dict[Tuple[str, str], dict]:
    """Compute a rolling-correlation summary for each symbol pair.

    For each pair we return the latest rolling correlation value, and simple
    statistics (mean, std) across the available rolling series.
    """
    df = _build_close_dataframe(frames)
    result: dict = {}
    if df.empty or df.shape[1] < 2:
        return result

    symbols = list(df.columns)
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            a = df[symbols[i]]
            b = df[symbols[j]]
            rolling = a.rolling(window).corr(b)
            rolling = rolling.dropna()
            if rolling.empty:
                continue
            key = (symbols[i], symbols[j])
            result[key] = {
                "latest": float(round(rolling.iloc[-1], 4)),
                "mean": float(round(rolling.mean(), 4)),
                "std": float(round(rolling.std(), 4)),
                "count": int(rolling.count()),
            }
    return result


def correlation_with_lag(
    a: pd.Series, b: pd.Series, max_lag: int = 5
) -> dict[str, Any]:
    """Find the lag (in periods) that maximizes absolute correlation between `a` and `b`.

    Positive lag means `a` leads `b` by that many periods (i.e., shift `a` forward).
    Returns the best lag, the correlation at that lag, and a small diagnostics dict.
    """
    best = {"lag": 0, "corr": 0.0}
    a = a.dropna()
    b = b.dropna()
    if a.empty or b.empty:
        return {"lag": 0, "corr": 0.0, "reason": "empty_series"}

    # align on common index for zero lag
    base = pd.concat([a, b], axis=1, join="inner")
    if base.shape[0] < 2:
        return {"lag": 0, "corr": 0.0, "reason": "insufficient_overlap"}

    for lag in range(-max_lag, max_lag + 1):
        if lag == 0:
            s = base.iloc[:, 0]
            t = base.iloc[:, 1]
        elif lag > 0:
            s = a.shift(lag).dropna()
            t = b.loc[s.index].dropna()
        else:
            t = b.shift(-lag).dropna()
            s = a.loc[t.index].dropna()

        if s.empty or t.empty:
            continue
        corr = s.corr(t)
        if pd.isna(corr):
            continue
        if abs(corr) > abs(best["corr"]):
            best = {"lag": lag, "corr": float(round(corr, 4))}

    return {**best}


def top_correlations(frames: dict[str, pd.DataFrame], top_n: int = 5):
    """Return the top positive and negative correlations from the pairwise matrix."""
    df = _build_close_dataframe(frames)
    if df.empty or df.shape[1] < 2:
        return {"positive": [], "negative": []}

    matrix = df.corr().fillna(0.0)
    pairs = []
    cols = matrix.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append((cols[i], cols[j], float(round(matrix.iat[i, j], 4))))

    sorted_pairs = sorted(pairs, key=lambda x: x[2], reverse=True)
    positive = [p for p in sorted_pairs if p[2] > 0][:top_n]
    negative = sorted(pairs, key=lambda x: x[2])[:top_n]
    return {"positive": positive, "negative": negative}


def correlation_snapshot(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """High-level snapshot used by other services.

    Provides a pairwise matrix plus top correlations and a rolling-summary
    for quick downstream scoring.
    """
    pairwise = compute_pairwise_correlations(frames)
    top = top_correlations(frames, top_n=5)
    rolling = rolling_correlation_summary(frames, window=50)

    return {
        "summary": pairwise.get("summary", "unknown"),
        "matrix": pairwise.get("correlations", {}),
        "top": top,
        "rolling_summary": {f"{a}-{b}": v for (a, b), v in rolling.items()},
    }
