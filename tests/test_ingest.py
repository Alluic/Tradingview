from io import StringIO

from tradingview_signal_dashboard.ingest import load_price_csv


def test_load_price_csv_infers_symbol_from_filename():
    csv = StringIO("date,open,high,low,close\n2024-01-01,1,2,0.5,1.5\n")
    frame = load_price_csv(csv, source_name="MMTW.csv")

    assert frame.loc[0, "symbol"] == "MMTW"
    assert frame.loc[0, "close"] == 1.5


def test_load_price_csv_accepts_column_aliases():
    csv = StringIO("time,price\n2024-01-01,42\n")
    frame = load_price_csv(csv, source_name="MMFI-export.csv")

    assert frame.loc[0, "symbol"] == "MMFI"
    assert frame.loc[0, "close"] == 42
