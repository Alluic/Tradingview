import pandas as pd

from tradingview_signal_dashboard.auto_data import compute_breadth_signals
from tradingview_signal_dashboard.config import load_config


def test_config_loads_automated_signal_settings():
    config = load_config()

    assert config.auto_data.enabled is True
    assert config.signals.moving_average_days["MMTW"] == 20
    assert config.signals.descriptions["MMTW"] == "Percent of stocks above 20-day moving average"
    assert config.alerts.signal_symbols == ("MMTW", "MMFI", "MMOH", "MMTH")
    assert config.alerts.zscore_thresholds == (1.0, 1.5, 2.0)


def test_compute_breadth_signals_percent_above_average():
    dates = pd.bdate_range("2024-01-01", periods=5)
    closes = pd.DataFrame(
        {
            "AAA": [1, 2, 3, 4, 5],
            "BBB": [5, 4, 3, 2, 1],
        },
        index=dates,
    )

    result = compute_breadth_signals(closes, {"TEST": 3}, min_coverage=1.0)

    assert set(result["symbol"]) == {"TEST"}
    assert result["date"].min() == dates[2]
    assert result.iloc[-1]["close"] == 50.0
