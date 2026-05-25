from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tradingview_signal_dashboard.indicators import add_signal_zscores


TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class SignalBacktestResult:
    rankings: pd.DataFrame
    detail: pd.DataFrame
    zscores: pd.DataFrame
    basket_returns: pd.Series


@dataclass(frozen=True)
class EventStudyResult:
    summary: pd.DataFrame
    events: pd.DataFrame


def build_weighted_basket_prices(etf_prices: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    if etf_prices.empty:
        return pd.Series(dtype=float, name="basket_close")

    prices = etf_prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices["symbol"] = prices["symbol"].astype(str).str.upper()
    pivot = prices.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()

    available_weights = {symbol: weight for symbol, weight in weights.items() if symbol in pivot.columns}
    if not available_weights:
        return pd.Series(dtype=float, name="basket_close")

    normalized_total = sum(available_weights.values())
    normalized = {symbol: weight / normalized_total for symbol, weight in available_weights.items()}
    selected = pivot[list(normalized)].dropna(how="any")
    if selected.empty:
        return pd.Series(dtype=float, name="basket_close")

    normalized_prices = selected / selected.iloc[0]
    basket = sum(normalized_prices[symbol] * weight for symbol, weight in normalized.items())
    basket.name = "basket_close"
    return basket


def _weekly_signal_rows(zscores: pd.DataFrame, symbol: str) -> pd.DataFrame:
    signal = zscores[zscores["symbol"] == symbol].copy()
    if signal.empty:
        return signal
    signal = signal.set_index("date").sort_index()
    weekly = signal.resample("W-FRI").last().dropna(subset=["z_score"])
    return weekly.reset_index()


def _next_trading_day(index: pd.DatetimeIndex, date: pd.Timestamp) -> pd.Timestamp | None:
    position = index.searchsorted(pd.Timestamp(date), side="right")
    if position >= len(index):
        return None
    return index[position]


def _future_trading_day(index: pd.DatetimeIndex, date: pd.Timestamp) -> pd.Timestamp | None:
    position = index.searchsorted(pd.Timestamp(date), side="left")
    if position >= len(index):
        return None
    return index[position]


def _forward_return(basket: pd.Series, execution_date: pd.Timestamp, weeks: int) -> float:
    target_date = execution_date + pd.Timedelta(days=weeks * 7)
    future_date = _future_trading_day(basket.index, target_date)
    if future_date is None or execution_date not in basket.index:
        return np.nan
    return float(basket.loc[future_date] / basket.loc[execution_date] - 1.0)


def _max_drawdown(nav: pd.Series) -> float:
    if nav.empty:
        return np.nan
    running_max = nav.cummax()
    drawdown = nav / running_max - 1.0
    return float(drawdown.min())


def _risk_metrics(strategy_returns: pd.Series) -> dict[str, float]:
    clean = strategy_returns.dropna()
    if clean.empty:
        return {
            "total_return": np.nan,
            "annualized_return": np.nan,
            "volatility": np.nan,
            "sharpe": np.nan,
            "sortino": np.nan,
            "max_drawdown": np.nan,
        }

    nav = (1.0 + clean).cumprod()
    total_return = float(nav.iloc[-1] - 1.0)
    years = len(clean) / TRADING_DAYS_PER_YEAR
    annualized_return = float((nav.iloc[-1] ** (1.0 / years)) - 1.0) if years > 0 else np.nan
    volatility = float(clean.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe = float((clean.mean() / clean.std(ddof=0)) * np.sqrt(TRADING_DAYS_PER_YEAR)) if clean.std(ddof=0) > 0 else np.nan
    downside = clean[clean < 0]
    sortino = float((clean.mean() / downside.std(ddof=0)) * np.sqrt(TRADING_DAYS_PER_YEAR)) if len(downside) > 1 and downside.std(ddof=0) > 0 else np.nan

    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": _max_drawdown(nav),
    }


def _strategy_returns_for_triggers(
    basket_returns: pd.Series,
    trigger_dates: list[pd.Timestamp],
    hold_weeks: int,
) -> pd.Series:
    exposure = pd.Series(0.0, index=basket_returns.index)
    for execution_date in trigger_dates:
        end_date = execution_date + pd.Timedelta(days=hold_weeks * 7)
        exposure.loc[(exposure.index >= execution_date) & (exposure.index <= end_date)] = 1.0
    return basket_returns.fillna(0.0) * exposure.shift(1).fillna(0.0)


def run_signal_backtests(
    signals: pd.DataFrame,
    etf_prices: pd.DataFrame,
    signal_symbols: list[str] | tuple[str, ...],
    etf_weights: dict[str, float],
    zscore_window: int,
    min_periods: int,
    trigger_threshold: float,
    hold_weeks: int,
    forward_weeks: list[int] | tuple[int, ...],
) -> SignalBacktestResult:
    basket = build_weighted_basket_prices(etf_prices, etf_weights)
    if basket.empty:
        empty = pd.DataFrame()
        return SignalBacktestResult(empty, empty, empty, pd.Series(dtype=float))

    basket_returns = basket.pct_change().fillna(0.0)
    zscores = add_signal_zscores(signals, window=zscore_window, min_periods=min_periods)

    rankings: list[dict[str, float | str | int]] = []
    details: list[dict[str, float | str | pd.Timestamp]] = []

    for symbol in signal_symbols:
        weekly = _weekly_signal_rows(zscores, symbol)
        if weekly.empty:
            rankings.append({"symbol": symbol, "status": "inactive_no_zscores", "trigger_count": 0})
            continue

        triggers = weekly[weekly["z_score"] < trigger_threshold].copy()
        execution_dates: list[pd.Timestamp] = []
        for _, row in triggers.iterrows():
            execution_date = _next_trading_day(basket.index, row["date"])
            if execution_date is None:
                continue
            execution_dates.append(execution_date)
            detail_row: dict[str, float | str | pd.Timestamp] = {
                "symbol": symbol,
                "signal_date": row["date"],
                "execution_date": execution_date,
                "signal_close": float(row["close"]),
                "z_score": float(row["z_score"]),
            }
            for weeks in forward_weeks:
                detail_row[f"forward_{weeks}w_return"] = _forward_return(basket, execution_date, weeks)
            details.append(detail_row)

        strategy_returns = _strategy_returns_for_triggers(basket_returns, execution_dates, hold_weeks=hold_weeks)
        metrics = _risk_metrics(strategy_returns)
        symbol_details = [row for row in details if row["symbol"] == symbol]
        forward_key = f"forward_{hold_weeks}w_return"
        forward_values = [float(row[forward_key]) for row in symbol_details if forward_key in row and pd.notna(row[forward_key])]

        rankings.append(
            {
                "symbol": symbol,
                "status": "active" if execution_dates else "active_no_triggers",
                "trigger_count": len(execution_dates),
                "exposure_pct": float((strategy_returns != 0).mean()),
                "win_rate": float(np.mean([value > 0 for value in forward_values])) if forward_values else np.nan,
                "avg_forward_return": float(np.mean(forward_values)) if forward_values else np.nan,
                **metrics,
            }
        )

    ranking_frame = pd.DataFrame(rankings)
    if not ranking_frame.empty:
        ranking_frame = ranking_frame.sort_values(
            by=["status", "sharpe", "sortino", "max_drawdown"],
            ascending=[True, False, False, False],
            na_position="last",
        ).reset_index(drop=True)

    detail_frame = pd.DataFrame(details)
    return SignalBacktestResult(ranking_frame, detail_frame, zscores, basket_returns)


def run_event_study(
    signals: pd.DataFrame,
    etf_prices: pd.DataFrame,
    signal_symbols: list[str] | tuple[str, ...],
    etf_weights: dict[str, float],
    zscore_window: int,
    min_periods: int,
    thresholds: list[float] | tuple[float, ...],
    forward_weeks: list[int] | tuple[int, ...],
) -> EventStudyResult:
    basket = build_weighted_basket_prices(etf_prices, etf_weights)
    if basket.empty:
        empty = pd.DataFrame()
        return EventStudyResult(empty, empty)

    zscores = add_signal_zscores(signals, window=zscore_window, min_periods=min_periods)
    events: list[dict[str, float | str | pd.Timestamp]] = []

    for symbol in signal_symbols:
        signal = (
            zscores[zscores["symbol"] == symbol]
            .dropna(subset=["z_score"])
            .sort_values("date")
            .copy()
        )
        if signal.empty:
            continue

        signal["previous_z_score"] = signal["z_score"].shift(1)
        signal = signal.dropna(subset=["previous_z_score"])
        for threshold in sorted(abs(float(threshold)) for threshold in thresholds):
            crossing_specs = (
                ("above", threshold, (signal["z_score"] >= threshold) & (signal["previous_z_score"] < threshold)),
                ("below", -threshold, (signal["z_score"] <= -threshold) & (signal["previous_z_score"] > -threshold)),
            )
            for direction, signed_threshold, mask in crossing_specs:
                for _, row in signal[mask].iterrows():
                    execution_date = _next_trading_day(basket.index, row["date"])
                    if execution_date is None:
                        continue
                    event: dict[str, float | str | pd.Timestamp] = {
                        "symbol": symbol,
                        "direction": direction,
                        "threshold": abs(signed_threshold),
                        "signal_date": pd.Timestamp(row["date"]),
                        "execution_date": execution_date,
                        "signal_close": float(row["close"]),
                        "z_score": float(row["z_score"]),
                        "previous_z_score": float(row["previous_z_score"]),
                    }
                    for weeks in forward_weeks:
                        event[f"forward_{weeks}w_return"] = _forward_return(basket, execution_date, weeks)
                    events.append(event)

    event_frame = pd.DataFrame(events)
    if event_frame.empty:
        return EventStudyResult(pd.DataFrame(), event_frame)

    summary_rows: list[dict[str, float | str | int | pd.Timestamp]] = []
    group_columns = ["symbol", "direction", "threshold"]
    for keys, group in event_frame.groupby(group_columns, sort=True):
        symbol, direction, threshold = keys
        for weeks in forward_weeks:
            column = f"forward_{weeks}w_return"
            returns = pd.to_numeric(group[column], errors="coerce").dropna()
            summary_rows.append(
                {
                    "symbol": symbol,
                    "direction": direction,
                    "threshold": threshold,
                    "horizon_weeks": int(weeks),
                    "event_count": int(len(returns)),
                    "avg_forward_return": float(returns.mean()) if not returns.empty else np.nan,
                    "median_forward_return": float(returns.median()) if not returns.empty else np.nan,
                    "win_rate": float((returns > 0).mean()) if not returns.empty else np.nan,
                    "best_forward_return": float(returns.max()) if not returns.empty else np.nan,
                    "worst_forward_return": float(returns.min()) if not returns.empty else np.nan,
                    "latest_signal_date": group["signal_date"].max(),
                }
            )

    summary = pd.DataFrame(summary_rows).sort_values(
        by=["symbol", "direction", "threshold", "horizon_weeks"]
    )
    return EventStudyResult(summary.reset_index(drop=True), event_frame.sort_values("signal_date", ascending=False))
