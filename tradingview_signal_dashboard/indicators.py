from __future__ import annotations

import numpy as np
import pandas as pd


def compute_rolling_zscore(
    values: pd.Series,
    window: int,
    min_periods: int | None = None,
) -> pd.DataFrame:
    """Return value, rolling mean/std, and z-score without future data."""
    if min_periods is None:
        min_periods = window

    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    rolling = numeric.rolling(window=window, min_periods=min_periods)
    mean = rolling.mean()
    std = rolling.std(ddof=0)
    z_score = (numeric - mean) / std.replace(0, np.nan)

    return pd.DataFrame(
        {
            "value": numeric,
            "rolling_mean": mean,
            "rolling_std": std,
            "z_score": z_score,
        },
        index=values.index,
    )


def add_signal_zscores(
    signals: pd.DataFrame,
    window: int,
    min_periods: int | None = None,
) -> pd.DataFrame:
    required = {"date", "symbol", "close"}
    missing = required - set(signals.columns)
    if missing:
        raise ValueError(f"Signal data missing required columns: {sorted(missing)}")

    frames: list[pd.DataFrame] = []
    clean = signals.copy()
    clean["date"] = pd.to_datetime(clean["date"])
    clean["symbol"] = clean["symbol"].astype(str).str.upper()
    clean = clean.sort_values(["symbol", "date"])

    for symbol, group in clean.groupby("symbol", sort=True):
        indexed = group.set_index("date")
        zscores = compute_rolling_zscore(indexed["close"], window=window, min_periods=min_periods)
        enriched = indexed.join(zscores[["rolling_mean", "rolling_std", "z_score"]])
        enriched["symbol"] = symbol
        frames.append(enriched.reset_index())

    if not frames:
        return pd.DataFrame(columns=[*clean.columns, "rolling_mean", "rolling_std", "z_score"])
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"])


def is_allocation_trigger(z_score: float, threshold: float = -1.0) -> bool:
    if pd.isna(z_score):
        return False
    return float(z_score) < threshold
