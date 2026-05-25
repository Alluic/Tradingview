import pandas as pd
import numpy as np

from tradingview_signal_dashboard.backtest import run_event_study, run_signal_backtests


def _signal_rows(symbol: str = "MMTW") -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=820)
    values = [50.0] * 756 + [20.0] * 64
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": symbol,
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "source_file": "test",
        }
    )


def _etf_rows() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=900)
    rows = []
    for symbol, base in {"VTI": 100, "SPY": 200}.items():
        for index, day in enumerate(dates):
            rows.append(
                {
                    "date": day,
                    "symbol": symbol,
                    "open": base + index,
                    "high": base + index,
                    "low": base + index,
                    "close": base + index,
                    "source_file": "test",
                }
            )
    return pd.DataFrame(rows)


def test_backtest_uses_same_etf_basket_and_ranks_active_signal():
    result = run_signal_backtests(
        signals=_signal_rows(),
        etf_prices=_etf_rows(),
        signal_symbols=("MMTW", "MMFI"),
        etf_weights={"VTI": 0.6, "SPY": 0.4},
        zscore_window=20,
        min_periods=20,
        trigger_threshold=-1.0,
        hold_weeks=8,
        forward_weeks=(4, 8, 12),
    )

    mmtw = result.rankings[result.rankings["symbol"] == "MMTW"].iloc[0]
    mmfi = result.rankings[result.rankings["symbol"] == "MMFI"].iloc[0]

    assert mmtw["status"] == "active"
    assert mmtw["trigger_count"] > 0
    assert mmfi["status"] == "inactive_no_zscores"
    assert not result.detail.empty


def test_event_study_counts_threshold_crossings_once():
    dates = pd.bdate_range("2020-01-01", periods=900)
    values = np.full(len(dates), 50.0)
    values[758] = 50.1
    values[820:823] = 65.0
    values[850:853] = 35.0
    signals = pd.DataFrame(
        {
            "date": dates,
            "symbol": "MMTW",
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "source_file": "test",
        }
    )

    result = run_event_study(
        signals=signals,
        etf_prices=_etf_rows(),
        signal_symbols=("MMTW",),
        etf_weights={"VTI": 0.6, "SPY": 0.4},
        zscore_window=60,
        min_periods=60,
        thresholds=(1.0, 1.5, 2.0),
        forward_weeks=(4, 8, 12),
    )

    events = result.events
    assert set(events["direction"]) == {"above", "below"}
    assert set(events["threshold"]) == {1.0, 1.5, 2.0}
    assert len(events[(events["direction"] == "above") & (events["threshold"] == 1.0)]) == 1
    assert len(events[(events["direction"] == "below") & (events["threshold"] == 1.0)]) == 1
    assert set(result.summary["horizon_weeks"]) == {4, 8, 12}
