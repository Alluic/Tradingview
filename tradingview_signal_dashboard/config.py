from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "defaults.yaml"


@dataclass(frozen=True)
class AutoDataConfig:
    enabled: bool
    source: str
    start_date: str
    end_date: str | None
    max_universe_symbols: int | None
    chunk_size: int
    min_price_coverage: float
    holdings_url: str


@dataclass(frozen=True)
class ZScoreConfig:
    window: int
    min_periods: int
    trigger_threshold: float


@dataclass(frozen=True)
class BacktestConfig:
    start_date: str | None
    end_date: str | None
    execution_lag_days: int
    research_hold_weeks: int
    zscore_thresholds: tuple[float, ...]
    forward_return_weeks: tuple[int, ...]


@dataclass(frozen=True)
class AllocationConfig:
    default_cash: float
    trigger_deploy_pct: float
    etf_weights: dict[str, float]


@dataclass(frozen=True)
class SmtpEnvConfig:
    host_env: str
    port_env: str
    username_env: str
    password_env: str
    from_env: str
    to_env: str
    use_tls_env: str


@dataclass(frozen=True)
class AlertConfig:
    enabled: bool
    signal_symbols: tuple[str, ...]
    zscore_thresholds: tuple[float, ...]
    send_on_cross_only: bool
    schedule_time: str
    email_subject_prefix: str
    smtp: SmtpEnvConfig


@dataclass(frozen=True)
class SignalConfig:
    default: str
    symbols: tuple[str, ...]
    moving_average_days: dict[str, int]
    descriptions: dict[str, str]


@dataclass(frozen=True)
class AppConfig:
    database_path: Path
    data_dir: Path
    auto_data: AutoDataConfig
    signals: SignalConfig
    zscore: ZScoreConfig
    backtest: BacktestConfig
    allocation: AllocationConfig
    alerts: AlertConfig


def _resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}

    signal_raw = raw["signals"]
    auto_raw = raw["auto_data"]
    zscore_raw = raw["zscore"]
    backtest_raw = raw["backtest"]
    allocation_raw = raw["allocation"]
    alerts_raw = raw["alerts"]
    smtp_raw = alerts_raw["smtp"]

    return AppConfig(
        database_path=_resolve_project_path(raw["database_path"]),
        data_dir=_resolve_project_path(raw["data_dir"]),
        auto_data=AutoDataConfig(
            enabled=bool(auto_raw["enabled"]),
            source=str(auto_raw["source"]),
            start_date=str(auto_raw["start_date"]),
            end_date=auto_raw.get("end_date"),
            max_universe_symbols=(
                None
                if auto_raw.get("max_universe_symbols") in (None, 0, "0")
                else int(auto_raw["max_universe_symbols"])
            ),
            chunk_size=int(auto_raw["chunk_size"]),
            min_price_coverage=float(auto_raw["min_price_coverage"]),
            holdings_url=str(auto_raw["holdings_url"]),
        ),
        signals=SignalConfig(
            default=str(signal_raw["default"]).upper(),
            symbols=tuple(str(symbol).upper() for symbol in signal_raw["symbols"]),
            moving_average_days={str(k).upper(): int(v) for k, v in signal_raw["moving_average_days"].items()},
            descriptions={str(k).upper(): str(v) for k, v in signal_raw["descriptions"].items()},
        ),
        zscore=ZScoreConfig(
            window=int(zscore_raw["window"]),
            min_periods=int(zscore_raw["min_periods"]),
            trigger_threshold=float(zscore_raw["trigger_threshold"]),
        ),
        backtest=BacktestConfig(
            start_date=backtest_raw.get("start_date"),
            end_date=backtest_raw.get("end_date"),
            execution_lag_days=int(backtest_raw["execution_lag_days"]),
            research_hold_weeks=int(backtest_raw["research_hold_weeks"]),
            zscore_thresholds=tuple(float(threshold) for threshold in backtest_raw["zscore_thresholds"]),
            forward_return_weeks=tuple(int(week) for week in backtest_raw["forward_return_weeks"]),
        ),
        allocation=AllocationConfig(
            default_cash=float(allocation_raw["default_cash"]),
            trigger_deploy_pct=float(allocation_raw["trigger_deploy_pct"]),
            etf_weights={str(k).upper(): float(v) for k, v in allocation_raw["etf_weights"].items()},
        ),
        alerts=AlertConfig(
            enabled=bool(alerts_raw["enabled"]),
            signal_symbols=tuple(str(symbol).upper() for symbol in alerts_raw.get("signal_symbols", [])),
            zscore_thresholds=tuple(float(threshold) for threshold in alerts_raw["zscore_thresholds"]),
            send_on_cross_only=bool(alerts_raw["send_on_cross_only"]),
            schedule_time=str(alerts_raw["schedule_time"]),
            email_subject_prefix=str(alerts_raw["email_subject_prefix"]),
            smtp=SmtpEnvConfig(
                host_env=str(smtp_raw["host_env"]),
                port_env=str(smtp_raw["port_env"]),
                username_env=str(smtp_raw["username_env"]),
                password_env=str(smtp_raw["password_env"]),
                from_env=str(smtp_raw["from_env"]),
                to_env=str(smtp_raw["to_env"]),
                use_tls_env=str(smtp_raw["use_tls_env"]),
            ),
        ),
    )
