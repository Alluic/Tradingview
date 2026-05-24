from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


PRICE_SCHEMA = """
    date DATE,
    symbol VARCHAR,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    source_file VARCHAR
"""


def connect(database_path: str | Path) -> duckdb.DuckDBPyConnection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    initialize(conn)
    return conn


def initialize(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(f"CREATE TABLE IF NOT EXISTS signal_prices ({PRICE_SCHEMA})")
    conn.execute(f"CREATE TABLE IF NOT EXISTS etf_prices ({PRICE_SCHEMA})")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sent_alerts (
            alert_key VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            signal_date DATE,
            z_score DOUBLE,
            close DOUBLE,
            sent_at TIMESTAMP,
            recipient VARCHAR
        )
        """
    )


def upsert_prices(conn: duckdb.DuckDBPyConnection, table: str, prices: pd.DataFrame) -> int:
    if table not in {"signal_prices", "etf_prices"}:
        raise ValueError(f"Unsupported table: {table}")
    if prices.empty:
        return 0

    required = ["date", "symbol", "open", "high", "low", "close", "source_file"]
    frame = prices[required].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["symbol"] = frame["symbol"].astype(str).str.upper()

    conn.register("incoming_prices", frame)
    conn.execute(
        f"""
        DELETE FROM {table}
        WHERE (date, symbol) IN (SELECT date, symbol FROM incoming_prices)
        """
    )
    conn.execute(f"INSERT INTO {table} SELECT * FROM incoming_prices")
    conn.unregister("incoming_prices")
    return len(frame)


def read_prices(conn: duckdb.DuckDBPyConnection, table: str) -> pd.DataFrame:
    if table not in {"signal_prices", "etf_prices"}:
        raise ValueError(f"Unsupported table: {table}")
    frame = conn.execute(f"SELECT * FROM {table} ORDER BY symbol, date").fetchdf()
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def clear_table(conn: duckdb.DuckDBPyConnection, table: str) -> None:
    if table not in {"signal_prices", "etf_prices"}:
        raise ValueError(f"Unsupported table: {table}")
    conn.execute(f"DELETE FROM {table}")


def alert_was_sent(conn: duckdb.DuckDBPyConnection, alert_key: str) -> bool:
    count = conn.execute(
        "SELECT COUNT(*) FROM sent_alerts WHERE alert_key = ?",
        [alert_key],
    ).fetchone()[0]
    return bool(count)


def record_sent_alert(
    conn: duckdb.DuckDBPyConnection,
    alert_key: str,
    symbol: str,
    signal_date: pd.Timestamp,
    z_score: float,
    close: float,
    recipient: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO sent_alerts
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """,
        [alert_key, symbol, pd.Timestamp(signal_date).date(), z_score, close, recipient],
    )


def symbol_summary(conn: duckdb.DuckDBPyConnection, table: str) -> pd.DataFrame:
    if table not in {"signal_prices", "etf_prices"}:
        raise ValueError(f"Unsupported table: {table}")
    return conn.execute(
        f"""
        SELECT
            symbol,
            COUNT(*) AS rows,
            MIN(date) AS first_date,
            MAX(date) AS last_date
        FROM {table}
        GROUP BY symbol
        ORDER BY symbol
        """
    ).fetchdf()
