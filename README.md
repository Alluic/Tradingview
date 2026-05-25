# TradingView Signal Research Dashboard

Research-first dashboard for testing market-breadth signals as manual ETF allocation signals.

GitHub target: `https://github.com/Alluic/Tradingview`. See [DEPLOYMENT.md](DEPLOYMENT.md) for Streamlit Cloud and GitHub Actions setup.

The first rule is intentionally simple:

```text
send alerts when rolling_z_score crosses +/-1.0, +/-1.5, or +/-2.0
```

Signals are evaluated on weekly closes. Backtests execute on the next available ETF trading day and rank candidate breadth signals by risk-adjusted performance.

## Quick Start

From this project folder:

```powershell
cd "C:\Users\ciull\Desktop\Coding Projects\Trading View"
pip install -r requirements.txt
pytest
streamlit run app.py
```

Running `python app.py` also delegates to Streamlit automatically, so IDE run buttons work.

After Streamlit starts, open the Local URL it prints, usually:

```text
http://localhost:8501
```

From the parent `Coding Projects` folder:

```powershell
python -m pip install -r "Trading View\requirements.txt"
python -m pytest "Trading View"
python -m streamlit run "Trading View\app.py"
```

You can also run:

```powershell
& ".\Trading View\run_dashboard.ps1"
```

## Automatic Email Alerts

The headless alert runner refreshes market data, recomputes z-scores, and sends one email per new trigger date when one of the monitored signals crosses a configured threshold.

Monitored alert signals:

- `MMTW`: Percent of stocks above 20-day moving average
- `MMFI`: Percent of stocks above 50-day moving average
- `MMOH`: Percent of stocks above 100-day moving average
- `MMTH`: Percent of stocks above 200-day moving average

Alert thresholds:

```text
z-score crosses above +1.0, +1.5, or +2.0
z-score crosses below -1.0, -1.5, or -2.0
```

Set email settings as user environment variables:

```powershell
[Environment]::SetEnvironmentVariable("TV_ALERT_SMTP_HOST", "smtp.gmail.com", "User")
[Environment]::SetEnvironmentVariable("TV_ALERT_SMTP_PORT", "587", "User")
[Environment]::SetEnvironmentVariable("TV_ALERT_SMTP_USERNAME", "your_email@gmail.com", "User")
[Environment]::SetEnvironmentVariable("TV_ALERT_SMTP_PASSWORD", "your_app_password", "User")
[Environment]::SetEnvironmentVariable("TV_ALERT_EMAIL_FROM", "your_email@gmail.com", "User")
[Environment]::SetEnvironmentVariable("TV_ALERT_EMAIL_TO", "jciulla55@gmail.com", "User")
[Environment]::SetEnvironmentVariable("TV_ALERT_SMTP_USE_TLS", "true", "User")
```

Run a dry check:

```powershell
cd "C:\Users\ciull\Desktop\Coding Projects\Trading View"
.\run_alert_check_dry.ps1
```

Install the weekday 6:00 PM scheduled task:

```powershell
cd "C:\Users\ciull\Desktop\Coding Projects\Trading View"
.\install_alert_task.ps1
```

The scheduled task runs `run_alert_check.ps1`, which sends email only when a new z-score trigger has not already been recorded.

## Data Inputs

By default, the app builds its own breadth signals automatically from public market data on first run:

- pulls a stock universe,
- downloads historical prices with `yfinance`,
- computes percent of stocks above 5, 20, 50, 100, 150, and 200-day moving averages,
- downloads ETF prices for `VTI`, `SPY`, `QQQ`, and `IWM`,
- runs the z-score signal backtest.

TradingView CSV exports are optional. Use them only if you want the exact TradingView index values instead of locally computed proxies. Optional exports should include:

```text
date, open, high, low, close, symbol
```

Only `date` and `close` are required. If `symbol` is missing, the importer infers it from the file name, such as `MMTW.csv`.

ETF price history can be downloaded from Yahoo Finance inside the dashboard or loaded from CSVs with the same shape.

To refresh data manually, open the `Data` page and click `Refresh automated market data`. Demo data is only a fallback for UI testing and is replaced automatically by real downloaded data.

If TradingView omits the `symbol` column, name each export after the signal, for example `MMTW.csv`.

## Research Model

- Candidate breadth symbols: `MMFD`, `MMTW`, `MMFI`, `MMOH`, `MMOF`, `MMTH`.
- Default visible signal: `MMTW`.
- Rolling z-score window: 756 trading days.
- Dashboard allocation preview threshold: `< -1.0`.
- Email alert thresholds: `+/-1.0`, `+/-1.5`, `+/-2.0` for `MMTW`, `MMFI`, `MMOH`, and `MMTH`.
- ETF basket: `40% VTI`, `25% SPY`, `25% QQQ`, `10% IWM`.
- Research ranking uses an 8-week tactical exposure window after each trigger so Sharpe, Sortino, and drawdown are comparable across signals.

This is decision-support tooling only. Fidelity execution remains manual.
