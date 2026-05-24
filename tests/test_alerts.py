import pandas as pd

from tradingview_signal_dashboard.alerts import format_alert_email, latest_signal_alerts
from tradingview_signal_dashboard.config import load_config


def test_latest_signal_alerts_requires_cross_below():
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

    assert [alert.symbol for alert in alerts] == ["MMTW"]
    assert alerts[0].z_score < config.zscore.trigger_threshold


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
