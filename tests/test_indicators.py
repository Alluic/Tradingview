import math

import pandas as pd

from tradingview_signal_dashboard.indicators import compute_rolling_zscore, is_allocation_trigger


def test_zscore_uses_minimum_history():
    values = pd.Series([10, 11, 12, 13])
    result = compute_rolling_zscore(values, window=3, min_periods=3)

    assert math.isnan(result.loc[0, "z_score"])
    assert math.isnan(result.loc[1, "z_score"])
    assert not math.isnan(result.loc[2, "z_score"])


def test_zscore_zero_std_returns_nan():
    values = pd.Series([10, 10, 10, 10])
    result = compute_rolling_zscore(values, window=3, min_periods=3)

    assert result["rolling_std"].iloc[-1] == 0
    assert math.isnan(result["z_score"].iloc[-1])


def test_trigger_is_strictly_less_than_threshold():
    assert not is_allocation_trigger(-1.0, -1.0)
    assert is_allocation_trigger(-1.0001, -1.0)
    assert not is_allocation_trigger(float("nan"), -1.0)
