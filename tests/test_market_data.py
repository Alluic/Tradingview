import pandas as pd

from tradingview_signal_dashboard.market_data import _normalize_history_frame


def test_normalize_history_frame_accepts_index_column_as_date():
    history = pd.DataFrame(
        {
            "Close": [100.0, 101.0],
        },
        index=pd.date_range("2024-01-01", periods=2),
    )

    normalized = _normalize_history_frame(history, "VTI")

    assert "date" in normalized.columns
    assert "close" in normalized.columns


def test_normalize_history_frame_accepts_datetime_index_name():
    history = pd.DataFrame(
        {
            "Adj Close": [100.0, 101.0],
        },
        index=pd.date_range("2024-01-01", periods=2, name="Datetime"),
    )

    normalized = _normalize_history_frame(history, "VTI")

    assert "date" in normalized.columns
    assert "adj close" in normalized.columns
