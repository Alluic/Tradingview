from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen
import csv
import re

import pandas as pd
import yfinance as yf


IWV_HOLDINGS_URL = (
    "https://www.ishares.com/ch/professionelle-anleger/de/produkte/239714/"
    "ishares-russell-3000-etf/1495092304805.ajax?fileType=csv&fileName=IWV_holdings&dataType=fund"
)

STOCKANALYSIS_IWV_HOLDINGS_URL = "https://stockanalysis.com/etf/iwv/holdings/"

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

SPECIAL_YAHOO_SYMBOLS = {
    "BFA": "BF-A",
    "BRKB": "BRK-B",
    "BFB": "BF-B",
    "GEFB": "GEF-B",
    "HEIA": "HEI-A",
    "LENB": "LEN-B",
    "MOGA": "MOG-A",
    "UHALB": "UHAL-B",
}


@dataclass(frozen=True)
class UniverseResult:
    symbols: list[str]
    source: str
    raw_count: int
    filtered_count: int


def _download_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/csv,text/html,*/*",
        },
    )
    with urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8-sig", errors="ignore")


def _normalize_yahoo_symbol(symbol: str) -> str | None:
    clean = str(symbol).strip().upper()
    if not clean or clean in {"-", "--", "NAN", "NONE"}:
        return None
    if clean in SPECIAL_YAHOO_SYMBOLS:
        return SPECIAL_YAHOO_SYMBOLS[clean]
    clean = clean.replace(".", "-")
    clean = re.sub(r"\s+", "-", clean)
    clean = re.sub(r"[^A-Z0-9-]", "", clean)
    return clean or None


def _is_equity_holding(row: dict[str, str]) -> bool:
    values = {str(key).strip().lower(): str(value).strip() for key, value in row.items()}
    ticker = values.get("ticker", values.get("emittententicker", ""))
    name = values.get("name", values.get("holding name", ""))
    asset_class = values.get("asset class", values.get("anlageklasse", ""))
    market = values.get("market", "")
    security_type = values.get("type", values.get("security type", ""))

    text = " ".join([ticker, name, asset_class, market, security_type]).upper()
    if not ticker or ticker in {"-", "--"}:
        return False
    if asset_class and asset_class.upper() not in {"EQUITY", "AKTIEN"}:
        return False
    excluded_terms = ("CASH", "FUTURE", "SWAP", "OPTION", "TREASURY", "COLLATERAL", "CURRENCY")
    return not any(term in text for term in excluded_terms)


def parse_ishares_holdings_csv(content: str) -> list[str]:
    if "<html" in content[:500].lower():
        raise ValueError("iShares holdings response was HTML, not CSV")

    lines = content.splitlines()
    header_index = None
    for index, line in enumerate(lines):
        columns = [column.strip().lower() for column in next(csv.reader([line]))]
        has_ticker = "ticker" in columns or "emittententicker" in columns
        if has_ticker and ("name" in columns or "holding name" in columns):
            header_index = index
            break
    if header_index is None:
        raise ValueError("Could not find a ticker header in iShares holdings CSV")

    reader = csv.DictReader(lines[header_index:])
    symbols: list[str] = []
    for row in reader:
        if not row or not _is_equity_holding(row):
            continue
        symbol = _normalize_yahoo_symbol(row.get("Ticker", row.get("Emittententicker", "")))
        if symbol:
            symbols.append(symbol)
    return list(dict.fromkeys(symbols))


def parse_stockanalysis_iwv_holdings_html(content: str) -> list[str]:
    body_match = re.search(r"<tbody.*?</tbody>", content, flags=re.IGNORECASE | re.DOTALL)
    if not body_match:
        raise ValueError("Could not find IWV holdings table in fallback HTML")
    symbols = re.findall(r'href="/stocks/([^"/]+)/"[^>]*>\s*([A-Za-z0-9.-]+)\s*</a>', body_match.group(0))
    normalized = [_normalize_yahoo_symbol(display or path) for path, display in symbols]
    return [symbol for symbol in dict.fromkeys(normalized) if symbol]


def get_iwv_universe(holdings_url: str = IWV_HOLDINGS_URL, max_symbols: int | None = None) -> UniverseResult:
    source = "ishares_iwv_holdings"
    try:
        symbols = parse_ishares_holdings_csv(_download_text(holdings_url))
    except Exception:
        source = "stockanalysis_iwv_holdings_fallback"
        try:
            symbols = parse_stockanalysis_iwv_holdings_html(_download_text(STOCKANALYSIS_IWV_HOLDINGS_URL))
        except Exception:
            source = "static_large_cap_fallback"
            symbols = FALLBACK_UNIVERSE.copy()

    raw_count = len(symbols)
    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    return UniverseResult(
        symbols=symbols,
        source=source,
        raw_count=raw_count,
        filtered_count=len(symbols),
    )


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
    chunk_size: int = 100,
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
    source: str = "auto_iwv_yfinance",
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
                "source_file": source,
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
    holdings_url: str = IWV_HOLDINGS_URL,
    min_coverage: float = 0.6,
) -> tuple[pd.DataFrame, UniverseResult]:
    universe = get_iwv_universe(holdings_url=holdings_url, max_symbols=max_symbols)
    closes = fetch_universe_closes(universe.symbols, start=start, end=end, chunk_size=chunk_size)
    if closes.empty:
        empty = pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "source_file"])
        return empty, universe
    return (
        compute_breadth_signals(
            closes,
            moving_average_days=moving_average_days,
            min_coverage=min_coverage,
            source=f"auto_{universe.source}",
        ),
        universe,
    )


def write_universe_snapshot(output_path: str | Path, universe: UniverseResult) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"symbol": universe.symbols}).to_csv(path, index=False)
