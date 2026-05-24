from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf


SP500_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

FALLBACK_UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "GOOG",
    "AVGO",
    "TSLA",
    "BRK-B",
    "LLY",
    "JPM",
    "V",
    "UNH",
    "XOM",
    "MA",
    "COST",
    "WMT",
    "HD",
    "PG",
    "NFLX",
    "JNJ",
    "ABBV",
    "BAC",
    "KO",
    "ORCL",
    "CRM",
    "MRK",
    "CVX",
    "AMD",
    "PEP",
    "TMO",
    "LIN",
    "MCD",
    "CSCO",
    "ADBE",
    "WFC",
    "ACN",
    "QCOM",
    "GE",
    "ABT",
    "IBM",
    "TXN",
    "CAT",
    "DHR",
    "VZ",
    "AMGN",
    "INTU",
    "PM",
    "NOW",
]


def get_sp500_universe(max_symbols: int | None = None) -> list[str]:
    try:
        tables = pd.read_html(SP500_WIKIPEDIA_URL)
        symbols = tables[0]["Symbol"].astype(str).str.replace(".", "-", regex=False).str.upper().tolist()
    except Exception:
        symbols = FALLBACK_UNIVERSE.copy()

    symbols = list(dict.fromkeys(symbols))
    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    return symbols


def _close_from_download(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(-1):
            close = raw.xs("Close", axis=1, level=-1)
        elif "Adj Close" in raw.columns.get_level_values(-1):
            close = raw.xs("Adj Close", axis=1, level=-1)
        else:
            return pd.DataFrame()
    else:
        column = "Close" if "Close" in raw.columns else "Adj Close"
        close = raw[[column]].rename(columns={column: symbols[0]})

    close.index = pd.to_datetime(close.index).normalize()
    close.columns = [str(column).upper() for column in close.columns]
    return close.apply(pd.to_numeric, errors="coerce")


def fetch_universe_closes(
    symbols: list[str],
    start: str | date,
    end: str | date | None = None,
    chunk_size: int = 75,
) -> pd.DataFrame:
    chunks: list[pd.DataFrame] = []
    for offset in range(0, len(symbols), chunk_size):
        chunk = symbols[offset : offset + chunk_size]
        raw = yf.download(
            tickers=chunk,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True,
            group_by="ticker",
            threads=True,
        )
        close = _close_from_download(raw, chunk)
        if not close.empty:
            chunks.append(close)

    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, axis=1).sort_index()


def compute_breadth_signals(
    closes: pd.DataFrame,
    moving_average_days: dict[str, int],
    min_coverage: float = 0.6,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    valid_counts = closes.notna().sum(axis=1)
    max_count = max(int(valid_counts.max()), 1)

    for symbol, window in moving_average_days.items():
        averages = closes.rolling(window=window, min_periods=window).mean()
        valid_signal = closes.notna() & averages.notna()
        valid_signal_counts = valid_signal.sum(axis=1)
        above = (closes > averages) & valid_signal
        coverage = valid_counts / max_count
        pct_above = above.sum(axis=1) / valid_signal_counts.replace(0, pd.NA) * 100
        pct_above = pct_above.where(coverage >= min_coverage)
        frame = pd.DataFrame(
            {
                "date": pct_above.index,
                "symbol": symbol,
                "open": pct_above.values,
                "high": pct_above.values,
                "low": pct_above.values,
                "close": pct_above.values,
                "source_file": "auto_sp500_yfinance",
            }
        ).dropna(subset=["close"])
        rows.append(frame)

    if not rows:
        return pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "source_file"])
    return pd.concat(rows, ignore_index=True).sort_values(["symbol", "date"])


def build_auto_breadth_signals(
    moving_average_days: dict[str, int],
    start: str | date,
    end: str | date | None,
    max_symbols: int | None,
    chunk_size: int,
) -> pd.DataFrame:
    universe = get_sp500_universe(max_symbols=max_symbols)
    closes = fetch_universe_closes(universe, start=start, end=end, chunk_size=chunk_size)
    if closes.empty:
        return pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "source_file"])
    return compute_breadth_signals(closes, moving_average_days=moving_average_days)
