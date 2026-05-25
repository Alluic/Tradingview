from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf


def _normalize_history_frame(history: pd.DataFrame, symbol: str) -> pd.DataFrame:
    history = history.reset_index()
    if isinstance(history.columns, pd.MultiIndex):
        history.columns = [column[0] for column in history.columns]

    normalized_columns = {}
    for column in history.columns:
        name = str(column).strip().lower().replace("_", " ")
        if name in {"date", "datetime", "index"}:
            normalized_columns[column] = "date"
        elif name in {"adj close", "adjclose"}:
            normalized_columns[column] = "adj close"
        else:
            normalized_columns[column] = name
    history = history.rename(columns=normalized_columns)

    if "date" not in history.columns:
        raise ValueError(
            f"Downloaded ETF history for {symbol} did not include a date column. "
            f"Columns: {list(history.columns)}"
        )
    if "close" not in history.columns and "adj close" not in history.columns:
        raise ValueError(
            f"Downloaded ETF history for {symbol} did not include a close column. "
            f"Columns: {list(history.columns)}"
        )
    return history


def fetch_etf_prices(
    symbols: list[str] | tuple[str, ...],
    start: str | date | None = None,
    end: str | date | None = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        history = yf.download(
            symbol,
            start=start,
            end=end,
            progress=False,
            auto_adjust=False,
            group_by="column",
            threads=False,
            multi_level_index=False,
        )
        if history.empty:
            continue
        history = _normalize_history_frame(history, symbol)
        close_column = "adj close" if "adj close" in history.columns else "close"
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(history["date"]).dt.normalize(),
                "symbol": symbol.upper(),
                "open": pd.to_numeric(history.get("open"), errors="coerce"),
                "high": pd.to_numeric(history.get("high"), errors="coerce"),
                "low": pd.to_numeric(history.get("low"), errors="coerce"),
                "close": pd.to_numeric(history[close_column], errors="coerce"),
                "source_file": "yfinance",
            }
        )
        frames.append(frame.dropna(subset=["date", "close"]))

    if not frames:
        return pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "source_file"])
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"])
