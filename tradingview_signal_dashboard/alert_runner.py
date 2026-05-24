from __future__ import annotations

import argparse
import sys

from tradingview_signal_dashboard.alerts import format_alert_email, latest_signal_alerts
from tradingview_signal_dashboard.auto_data import build_auto_breadth_signals
from tradingview_signal_dashboard.config import load_config
from tradingview_signal_dashboard.emailer import load_email_settings, send_email
from tradingview_signal_dashboard.market_data import fetch_etf_prices
from tradingview_signal_dashboard.storage import alert_was_sent, connect, read_prices, record_sent_alert, upsert_prices


def refresh_market_data() -> tuple[int, int]:
    config = load_config()
    conn = connect(config.database_path)
    signal_rows = build_auto_breadth_signals(
        moving_average_days=config.signals.moving_average_days,
        start=config.auto_data.start_date,
        end=config.auto_data.end_date,
        max_symbols=config.auto_data.max_universe_symbols,
        chunk_size=config.auto_data.chunk_size,
    )
    etf_rows = fetch_etf_prices(
        list(config.allocation.etf_weights),
        start=config.auto_data.start_date,
        end=config.auto_data.end_date,
    )
    return upsert_prices(conn, "signal_prices", signal_rows), upsert_prices(conn, "etf_prices", etf_rows)


def run_alert_check(send: bool = True, dry_run: bool = False) -> int:
    config = load_config()
    if not config.alerts.enabled:
        print("Alerts are disabled in config.")
        return 0

    signal_count, etf_count = refresh_market_data()
    print(f"Updated {signal_count:,} breadth rows and {etf_count:,} ETF rows.")

    conn = connect(config.database_path)
    alerts = latest_signal_alerts(read_prices(conn, "signal_prices"), config)
    unsent = [alert for alert in alerts if not alert_was_sent(conn, alert.alert_key)]

    if not unsent:
        print("No new z-score alerts.")
        return 0

    subject, body = format_alert_email(unsent, config)
    print(subject)
    print(body)

    if dry_run or not send:
        print("Dry run only; no email sent and alert state was not recorded.")
        return len(unsent)

    settings = load_email_settings(config.alerts.smtp)
    send_email(settings, subject, body)
    for alert in unsent:
        record_sent_alert(
            conn,
            alert_key=alert.alert_key,
            symbol=alert.symbol,
            signal_date=alert.signal_date,
            z_score=alert.z_score,
            close=alert.close,
            recipient=settings.recipient,
        )
    print(f"Sent {len(unsent)} alert(s) to {settings.recipient}.")
    return len(unsent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh market data and email new z-score alerts.")
    parser.add_argument("--dry-run", action="store_true", help="Print alert email content without sending.")
    parser.add_argument("--no-email", action="store_true", help="Refresh and print alerts without sending email.")
    args = parser.parse_args(argv)

    try:
        run_alert_check(send=not args.no_email, dry_run=args.dry_run)
    except Exception as exc:
        print(f"Alert runner failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
