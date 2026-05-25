import pandas as pd

from tradingview_signal_dashboard.alerts import format_alert_email, latest_signal_alerts
from tradingview_signal_dashboard.config import load_config


def test_latest_signal_alerts_requires_cross_below_thresholds():
    config = load_config()
    dates = pd.bdate_range("2020-01-01", periods=820)
    values = [50.0] * 819 + [20.0]
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

    alerts = latest_signal_alerts(signals, config)

    assert [alert.symbol for alert in alerts] == ["MMTW", "MMTW", "MMTW"]
    assert [alert.direction for alert in alerts] == ["below", "below", "below"]
    assert [alert.threshold for alert in alerts] == [1.0, 1.5, 2.0]


def test_format_alert_email_includes_allocation():
    config = load_config()
    dates = pd.bdate_range("2020-01-01", periods=820)
    values = [50.0] * 819 + [20.0]
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
    alert = latest_signal_alerts(signals, config)[0]

    subject, body = format_alert_email([alert], config)

    assert "MMTW" in subject
    assert "Suggested allocation" in body
    assert "Execution remains manual" in body


def test_latest_signal_alerts_detects_cross_above_thresholds():
    config = load_config()
    dates = pd.bdate_range("2020-01-01", periods=820)
    values = [50.0] * 819 + [80.0]
    signals = pd.DataFrame(
        {
            "date": dates,
            "symbol": "MMFI",
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "source_file": "test",
        }
    )

    alerts = latest_signal_alerts(signals, config)

    assert [alert.symbol for alert in alerts] == ["MMFI", "MMFI", "MMFI"]
    assert [alert.direction for alert in alerts] == ["above", "above", "above"]
    assert [alert.threshold for alert in alerts] == [1.0, 1.5, 2.0]
