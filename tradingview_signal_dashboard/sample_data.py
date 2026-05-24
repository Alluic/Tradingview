from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def make_sample_signals(symbols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    dates = pd.bdate_range("2014-01-02", "2026-05-22")
    cycle = np.sin(np.linspace(0, 24 * np.pi, len(dates)))
    slow_cycle = np.sin(np.linspace(0, 7 * np.pi, len(dates)))
    shock = np.zeros(len(dates))
    for start, length, depth in ((520, 45, -28), (1580, 65, -34), (2250, 50, -30), (3020, 40, -26)):
        end = min(start + length, len(dates))
        shock[start:end] += np.linspace(depth, 0, end - start)

    rows: list[pd.DataFrame] = []
    for index, symbol in enumerate(symbols):
        phase = index * 0.65
        amplitude = 14 + index * 2.5
        values = 52 + amplitude * np.sin(np.linspace(phase, 24 * np.pi + phase, len(dates)))
        values += 8 * slow_cycle + shock * (1.0 - index * 0.07)
        values = np.clip(values, 2, 98)
        frame = pd.DataFrame(
            {
                "date": dates,
                "symbol": symbol,
                "open": values,
                "high": np.clip(values + 2.0, 0, 100),
                "low": np.clip(values - 2.0, 0, 100),
                "close": values,
                "source_file": "demo_generated",
            }
        )
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def make_sample_etfs(weights: dict[str, float]) -> pd.DataFrame:
    dates = pd.bdate_range("2014-01-02", "2026-05-22")
    market = np.cumprod(1 + 0.00035 + 0.008 * np.sin(np.linspace(0, 18 * np.pi, len(dates))) / 100)
    rows: list[pd.DataFrame] = []
    for index, symbol in enumerate(weights):
        drift = 0.00028 + index * 0.00003
        wiggle = 0.0016 * np.sin(np.linspace(index, 42 * np.pi + index, len(dates)))
        returns = drift + wiggle
        prices = 100 * market * np.cumprod(1 + returns)
        frame = pd.DataFrame(
            {
                "date": dates,
                "symbol": symbol,
                "open": prices,
                "high": prices * 1.004,
                "low": prices * 0.996,
                "close": prices,
                "source_file": "demo_generated",
            }
        )
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def write_sample_signal_exports(output_dir: str | Path, symbols: tuple[str, ...] | list[str]) -> list[Path]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    signals = make_sample_signals(symbols)
    written: list[Path] = []
    for symbol, frame in signals.groupby("symbol"):
        file_path = path / f"{symbol}.csv"
        frame[["date", "open", "high", "low", "close", "symbol"]].to_csv(file_path, index=False)
        written.append(file_path)
    return written
