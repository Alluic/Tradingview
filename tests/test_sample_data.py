from tradingview_signal_dashboard.sample_data import make_sample_etfs, make_sample_signals


def test_sample_signals_cover_requested_symbols():
    frame = make_sample_signals(("MMTW", "MMFI"))

    assert set(frame["symbol"]) == {"MMTW", "MMFI"}
    assert {"date", "open", "high", "low", "close", "symbol", "source_file"} <= set(frame.columns)
    assert frame["close"].between(0, 100).all()


def test_sample_etfs_cover_weight_symbols():
    frame = make_sample_etfs({"VTI": 0.6, "SPY": 0.4})

    assert set(frame["symbol"]) == {"VTI", "SPY"}
    assert frame["close"].min() > 0
