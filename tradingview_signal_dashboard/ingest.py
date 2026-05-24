from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, TextIO

import pandas as pd


PRICE_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "source_file"]
COLUMN_ALIASES = {
    "time": "date",
    "datetime": "date",
    "timestamp": "date",
    "last": "close",
    "price": "close",
}


def _normalize_columns(columns: list[str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for column in columns:
        key = str(column).strip().lower().replace(" ", "_")
        normalized[column] = COLUMN_ALIASES.get(key, key)
    return normalized


def _infer_symbol(source_name: str) -> str:
    stem = Path(source_name).stem.upper()
    for separator in ("_", "-", " "):
        if separator in stem:
            return stem.split(separator)[0]
    return stem


def load_price_csv(source: str | Path | TextIO | BinaryIO, source_name: str | None = None) -> pd.DataFrame:
    if source_name is None:
        source_name = Path(source).name if isinstance(source, (str, Path)) else "uploaded.csv"

    frame = pd.read_csv(source)
    frame = frame.rename(columns=_normalize_columns(list(frame.columns)))

    if "date" not in frame.columns:
        raise ValueError(f"{source_name} is missing a date column")
    if "close" not in frame.columns:
        raise ValueError(f"{source_name} is missing a close column")

    if "symbol" not in frame.columns:
        frame["symbol"] = _infer_symbol(source_name)

    for column in ("open", "high", "low", "close"):
        if column not in frame.columns:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["source_file"] = source_name
    frame = frame.dropna(subset=["date", "close", "symbol"])
    frame = frame[PRICE_COLUMNS].sort_values(["symbol", "date"])

    if frame.empty:
        raise ValueError(f"{source_name} did not contain any valid dated close values")
    return frame.reset_index(drop=True)


def load_price_folder(folder: str | Path) -> pd.DataFrame:
    folder_path = Path(folder)
    frames = [load_price_csv(path, source_name=path.name) for path in sorted(folder_path.glob("*.csv"))]
    if not frames:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    return pd.concat(frames, ignore_index=True).drop_duplicates(["date", "symbol"], keep="last")
