import pandas as pd

from tradingview_signal_dashboard.auto_data import compute_breadth_signals, parse_ishares_holdings_csv
from tradingview_signal_dashboard.config import load_config


def test_config_loads_automated_signal_settings():
    config = load_config()

    assert config.auto_data.enabled is True
    assert config.auto_data.source == "ishares_iwv_holdings"
    assert config.auto_data.min_price_coverage == 0.60
    assert "ishares.com" in config.auto_data.holdings_url
    assert config.signals.moving_average_days["MMTW"] == 20
    assert config.signals.descriptions["MMTW"] == "Percent of stocks above 20-day moving average"
    assert config.alerts.signal_symbols == ("MMTW", "MMFI", "MMOH", "MMTH")
    assert config.alerts.zscore_thresholds == (1.0, 1.5, 2.0)
    assert config.backtest.zscore_thresholds == (1.0, 1.5, 2.0)


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


def test_parse_ishares_holdings_filters_to_yahoo_equities():
    content = """iShares Russell 3000 ETF
Generated,2026-05-25
Ticker,Name,Asset Class,Market Value,Weight (%)
AAPL,APPLE INC,EQUITY,100,5.0
BRK.B,BERKSHIRE HATHAWAY INC,EQUITY,80,4.0
 ,BLANK TICKER,EQUITY,1,0.1
USD,CASH COLLATERAL,CASH,5,0.2
ESM6,S&P 500 EMINI FUTURE,EQUITY,2,0.1
"""

    assert parse_ishares_holdings_csv(content) == ["AAPL", "BRK-B"]


def test_parse_ishares_holdings_accepts_iwv_localized_csv():
    content = """iShares Russell 3000 ETF
Fondsposition per,"22.Mai2026"
Stock,"-"
 
Emittententicker,Name,Sektor,Anlageklasse,Marktwert,Gewichtung (%)
NVDA,NVIDIA CORP,IT,Aktien,100,7.0
BRKB,BERKSHIRE HATHAWAY INC,Financials,Aktien,80,1.2
USD,US DOLLAR,Cash,Cash,1,0.1
"""

    assert parse_ishares_holdings_csv(content) == ["NVDA", "BRK-B"]
