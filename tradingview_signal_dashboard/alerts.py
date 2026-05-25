from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tradingview_signal_dashboard.allocation import allocation_preview
from tradingview_signal_dashboard.config import AppConfig
from tradingview_signal_dashboard.indicators import add_signal_zscores


@dataclass(frozen=True)
class SignalAlert:
    alert_key: str
    symbol: str
    direction: str
    threshold: float
    signal_date: pd.Timestamp
    close: float
    z_score: float
    previous_z_score: float | None
    allocation: pd.DataFrame


def latest_signal_alerts(signals: pd.DataFrame, config: AppConfig) -> list[SignalAlert]:
    if signals.empty:
        return []

    zscores = add_signal_zscores(
        signals,
        window=config.zscore.window,
        min_periods=config.zscore.min_periods,
    )
    symbols = config.alerts.signal_symbols or config.signals.symbols
    alerts: list[SignalAlert] = []

    for symbol in symbols:
        rows = (
            zscores[zscores["symbol"] == symbol]
            .dropna(subset=["z_score"])
            .sort_values("date")
            .tail(2)
        )
        if rows.empty:
            continue

        latest = rows.iloc[-1]
        previous = rows.iloc[-2] if len(rows) > 1 else None
        z_score = float(latest["z_score"])
        previous_z_score = None if previous is None else float(previous["z_score"])
        signal_date = pd.Timestamp(latest["date"])
        for threshold in sorted(config.alerts.zscore_thresholds):
            for direction, signed_threshold in (("above", threshold), ("below", -threshold)):
                if direction == "above":
                    triggered = z_score >= signed_threshold
                    already_triggered = previous_z_score is not None and previous_z_score >= signed_threshold
                else:
                    triggered = z_score <= signed_threshold
                    already_triggered = previous_z_score is not None and previous_z_score <= signed_threshold

                if not triggered:
                    continue
                if config.alerts.send_on_cross_only and already_triggered:
                    continue

                allocation = allocation_preview(
                    cash=config.allocation.default_cash,
                    latest_z_score=z_score,
                    threshold=-threshold,
                    etf_weights=config.allocation.etf_weights,
                    deploy_pct=config.allocation.trigger_deploy_pct,
                )
                alerts.append(
                    SignalAlert(
                        alert_key=f"{symbol}:{signal_date.date()}:{direction}:{threshold}",
                        symbol=symbol,
                        direction=direction,
                        threshold=threshold,
                        signal_date=signal_date,
                        close=float(latest["close"]),
                        z_score=z_score,
                        previous_z_score=previous_z_score,
                        allocation=allocation,
                    )
                )
    return alerts


def format_alert_email(alerts: list[SignalAlert], config: AppConfig) -> tuple[str, str]:
    symbols = ", ".join(f"{alert.symbol} {alert.direction} {alert.threshold:g}σ" for alert in alerts)
    subject = f"{config.alerts.email_subject_prefix}: {symbols}"
    sections = [
        "Market breadth z-score trigger(s) are active.",
        "",
        f"Alert thresholds: {', '.join(f'+/-{threshold:g}' for threshold in config.alerts.zscore_thresholds)}",
        f"Default deploy cash: ${config.allocation.default_cash:,.2f}",
        "",
    ]
    for alert in alerts:
        sections.extend(
            [
                f"{alert.symbol}",
                f"  Signal date: {alert.signal_date.date()}",
                f"  Trigger: z-score {alert.direction} {'+' if alert.direction == 'above' else '-'}{alert.threshold:g}",
                f"  Breadth close: {alert.close:.2f}",
                f"  Z-score: {alert.z_score:.2f}",
                f"  Previous z-score: {'n/a' if alert.previous_z_score is None else f'{alert.previous_z_score:.2f}'}",
            ]
        )
        if alert.direction == "below":
            sections.append("  Suggested allocation:")
            for _, row in alert.allocation.iterrows():
                sections.append(
                    f"    {row['symbol']}: {row['weight']:.0%} / ${row['allocation_dollars']:,.2f}"
                )
        else:
            sections.append("  Allocation note: positive z-score alert; no buy allocation is generated.")
        sections.append("")
    sections.append("Broker execution remains manual.")
    return subject, "\n".join(sections)
