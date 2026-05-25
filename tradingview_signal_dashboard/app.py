from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from tradingview_signal_dashboard.allocation import allocation_preview
from tradingview_signal_dashboard.auto_data import build_auto_breadth_signals
from tradingview_signal_dashboard.backtest import run_event_study, run_signal_backtests
from tradingview_signal_dashboard.config import load_config
from tradingview_signal_dashboard.ingest import load_price_csv
from tradingview_signal_dashboard.market_data import fetch_etf_prices
from tradingview_signal_dashboard.sample_data import make_sample_etfs, make_sample_signals, write_sample_signal_exports
from tradingview_signal_dashboard.storage import clear_table, connect, read_metadata, read_prices, set_metadata, symbol_summary, upsert_prices


def _format_percent_columns(frame: pd.DataFrame) -> pd.DataFrame:
    percent_columns = [
        "total_return",
        "annualized_return",
        "volatility",
        "max_drawdown",
        "win_rate",
        "avg_forward_return",
        "median_forward_return",
        "best_forward_return",
        "worst_forward_return",
        "exposure_pct",
    ]
    display = frame.copy()
    percent_columns.extend([column for column in display.columns if column.startswith("forward_") and column.endswith("_return")])
    for column in percent_columns:
        if column in display.columns:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.2%}")
    for column in ("sharpe", "sortino"):
        if column in display.columns:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
    return display


def _signal_label(symbol: str, config) -> str:
    description = config.signals.descriptions.get(symbol, "")
    return f"{symbol} - {description}" if description else symbol


def _with_signal_description(frame: pd.DataFrame, config) -> pd.DataFrame:
    if frame.empty or "symbol" not in frame.columns:
        return frame
    display = frame.copy()
    display.insert(
        display.columns.get_loc("symbol") + 1,
        "description",
        display["symbol"].map(lambda symbol: config.signals.descriptions.get(str(symbol), "")),
    )
    return display


@st.cache_data(show_spinner=False)
def _run_cached_backtest(
    signals: pd.DataFrame,
    etfs: pd.DataFrame,
    signal_symbols: tuple[str, ...],
    etf_weights_items: tuple[tuple[str, float], ...],
    window: int,
    min_periods: int,
    threshold: float,
    hold_weeks: int,
    forward_weeks: tuple[int, ...],
):
    return run_signal_backtests(
        signals=signals,
        etf_prices=etfs,
        signal_symbols=signal_symbols,
        etf_weights=dict(etf_weights_items),
        zscore_window=window,
        min_periods=min_periods,
        trigger_threshold=threshold,
        hold_weeks=hold_weeks,
        forward_weeks=forward_weeks,
    )


@st.cache_data(show_spinner=False)
def _run_cached_event_study(
    signals: pd.DataFrame,
    etfs: pd.DataFrame,
    signal_symbols: tuple[str, ...],
    etf_weights_items: tuple[tuple[str, float], ...],
    window: int,
    min_periods: int,
    thresholds: tuple[float, ...],
    forward_weeks: tuple[int, ...],
):
    return run_event_study(
        signals=signals,
        etf_prices=etfs,
        signal_symbols=signal_symbols,
        etf_weights=dict(etf_weights_items),
        zscore_window=window,
        min_periods=min_periods,
        thresholds=thresholds,
        forward_weeks=forward_weeks,
    )


def _upload_prices(label: str, table: str, conn) -> None:
    files = st.file_uploader(label, type=["csv"], accept_multiple_files=True)
    if not files:
        return
    frames = []
    errors = []
    for file in files:
        try:
            frames.append(load_price_csv(file, source_name=file.name))
        except ValueError as exc:
            errors.append(str(exc))
    if frames:
        inserted = upsert_prices(conn, table, pd.concat(frames, ignore_index=True))
        st.success(f"Loaded {inserted:,} rows into {table}.")
        st.cache_data.clear()
        st.rerun()
    for error in errors:
        st.warning(error)


def _needs_automated_data(conn) -> bool:
    signals = read_prices(conn, "signal_prices")
    etfs = read_prices(conn, "etf_prices")
    if signals.empty or etfs.empty:
        return True
    signal_sources = set(signals["source_file"].dropna().astype(str))
    etf_sources = set(etfs["source_file"].dropna().astype(str))
    return signal_sources == {"demo_generated"} or etf_sources == {"demo_generated"}


def _load_automated_market_data(conn, config, clear_existing: bool = False) -> tuple[int, int]:
    if clear_existing:
        clear_table(conn, "signal_prices")
        clear_table(conn, "etf_prices")

    signal_rows, universe = build_auto_breadth_signals(
        moving_average_days=config.signals.moving_average_days,
        start=config.auto_data.start_date,
        end=config.auto_data.end_date,
        max_symbols=config.auto_data.max_universe_symbols,
        chunk_size=config.auto_data.chunk_size,
        holdings_url=config.auto_data.holdings_url,
        min_coverage=config.auto_data.min_price_coverage,
    )
    etf_rows = fetch_etf_prices(
        list(config.allocation.etf_weights),
        start=config.auto_data.start_date,
        end=config.auto_data.end_date,
    )
    signal_count = upsert_prices(conn, "signal_prices", signal_rows)
    etf_count = upsert_prices(conn, "etf_prices", etf_rows)
    set_metadata(
        conn,
        {
            "universe_source": universe.source,
            "universe_raw_count": universe.raw_count,
            "universe_filtered_count": universe.filtered_count,
            "universe_last_refresh": pd.Timestamp.now(tz="UTC").isoformat(),
            "auto_data_source": config.auto_data.source,
            "signal_rows_last_loaded": signal_count,
            "etf_rows_last_loaded": etf_count,
        },
    )
    st.cache_data.clear()
    return signal_count, etf_count


def _ensure_automated_data(conn, config) -> None:
    if not config.auto_data.enabled or not _needs_automated_data(conn):
        return

    with st.status("Building market breadth signals automatically...", expanded=True) as status:
        st.write("Fetching stock universe and price history from public market data.")
        st.write("Computing percent-above-moving-average breadth signals.")
        st.write("Downloading ETF history for the allocation basket.")
        signal_count, etf_count = _load_automated_market_data(conn, config, clear_existing=True)
        if signal_count and etf_count:
            status.update(
                label=f"Loaded {signal_count:,} breadth rows and {etf_count:,} ETF rows.",
                state="complete",
                expanded=False,
            )
            st.rerun()
        else:
            status.update(label="Automatic data load did not return enough rows.", state="error", expanded=True)


def _missing_data_panel(conn, config, context: str) -> None:
    signal_summary = symbol_summary(conn, "signal_prices")
    etf_summary = symbol_summary(conn, "etf_prices")
    loaded_signals = set(signal_summary["symbol"]) if not signal_summary.empty else set()
    loaded_etfs = set(etf_summary["symbol"]) if not etf_summary.empty else set()
    missing_signals = [symbol for symbol in config.signals.symbols if symbol not in loaded_signals]
    missing_etfs = [symbol for symbol in config.allocation.etf_weights if symbol not in loaded_etfs]

    st.info(f"{context} needs breadth signal history and ETF price history.")
    st.markdown(
        """
        **Next steps**
        1. Open the `Data` page in the sidebar.
        2. Click `Refresh automated market data` to rebuild public-data breadth signals.
        3. Optional: upload TradingView CSV exports if you want to compare against TradingView's exact index history.
        4. Return to `Signal Research` to rank the signals.
        """
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Signal CSV status")
        status = pd.DataFrame(
            {
                "symbol": list(config.signals.symbols),
                "description": [_signal_label(symbol, config).split(" - ", 1)[1] for symbol in config.signals.symbols],
                "loaded": [symbol in loaded_signals for symbol in config.signals.symbols],
            }
        )
        st.dataframe(status, use_container_width=True, hide_index=True)
        if missing_signals:
            st.caption(f"Missing: {', '.join(missing_signals)}")

    with right:
        st.subheader("ETF price status")
        status = pd.DataFrame(
            {
                "symbol": list(config.allocation.etf_weights),
                "loaded": [symbol in loaded_etfs for symbol in config.allocation.etf_weights],
            }
        )
        st.dataframe(status, use_container_width=True, hide_index=True)
        if missing_etfs:
            st.caption(f"Missing: {', '.join(missing_etfs)}")


def _data_manager(conn, config) -> None:
    st.header("Data")
    st.write("The app can build breadth signals automatically from public market data. Uploads are optional.")

    with st.expander("Automated market data", expanded=True):
        st.write(
            "This downloads a stock universe, computes percent-above-moving-average breadth signals, "
            "downloads ETF prices, and refreshes the research database."
        )
        metadata = read_metadata(conn)
        auto_left, auto_mid, auto_right = st.columns(3)
        with auto_left:
            st.metric("Universe source", metadata.get("universe_source", config.auto_data.source))
            st.metric("Universe cap", config.auto_data.max_universe_symbols or "All")
            st.metric("Minimum coverage", f"{config.auto_data.min_price_coverage:.0%}")
        with auto_mid:
            st.metric("Raw holdings", metadata.get("universe_raw_count", "n/a"))
            st.metric("Active universe", metadata.get("universe_filtered_count", "n/a"))
        with auto_right:
            st.metric("Start date", config.auto_data.start_date)
            st.metric("Last refresh", metadata.get("universe_last_refresh", "n/a"))
        st.caption(f"ETF basket: {', '.join(config.allocation.etf_weights)}")
        if st.button("Refresh automated market data", type="primary"):
            with st.spinner("Downloading and computing automated market data..."):
                signal_count, etf_count = _load_automated_market_data(conn, config, clear_existing=True)
            st.success(f"Loaded {signal_count:,} breadth rows and {etf_count:,} ETF rows.")
            st.rerun()

    with st.expander("Demo data and optional files", expanded=False):
        st.write(
            "Use generated demo data to confirm the research, detail, and allocation pages work. "
            "Replace it with real TradingView exports before trusting any signal ranking."
        )
        demo_left, demo_right, demo_clear = st.columns(3)
        with demo_left:
            if st.button("Load demo data", type="primary"):
                clear_table(conn, "signal_prices")
                clear_table(conn, "etf_prices")
                signal_rows = make_sample_signals(config.signals.symbols)
                etf_rows = make_sample_etfs(config.allocation.etf_weights)
                upsert_prices(conn, "signal_prices", signal_rows)
                upsert_prices(conn, "etf_prices", etf_rows)
                st.cache_data.clear()
                st.rerun()
        with demo_right:
            if st.button("Create sample CSV exports"):
                output_dir = config.data_dir / "sample_tradingview_exports"
                paths = write_sample_signal_exports(output_dir, config.signals.symbols)
                st.success(f"Created {len(paths)} CSV files in {output_dir}.")
        with demo_clear:
            if st.button("Clear loaded data"):
                clear_table(conn, "signal_prices")
                clear_table(conn, "etf_prices")
                st.cache_data.clear()
                st.rerun()

    left, right = st.columns(2)
    with left:
        st.subheader("TradingView Signals")
        _upload_prices("Upload signal CSV exports", "signal_prices", conn)
        summary = symbol_summary(conn, "signal_prices")
        st.dataframe(_with_signal_description(summary, config), use_container_width=True, hide_index=True)

    with right:
        st.subheader("ETF Prices")
        _upload_prices("Upload ETF price CSV exports", "etf_prices", conn)
        symbols = list(config.allocation.etf_weights)
        start = st.date_input("Download start date", value=date(2010, 1, 1))
        end = st.date_input("Download end date", value=date.today())
        if st.button("Download ETF prices", type="primary"):
            prices = fetch_etf_prices(symbols, start=start, end=end)
            if prices.empty:
                st.warning("No ETF prices were downloaded.")
            else:
                inserted = upsert_prices(conn, "etf_prices", prices)
                st.success(f"Loaded {inserted:,} ETF price rows.")
                st.cache_data.clear()
                st.rerun()
        summary = symbol_summary(conn, "etf_prices")
        st.dataframe(summary, use_container_width=True, hide_index=True)


def _load_backtest(conn, config):
    signals = read_prices(conn, "signal_prices")
    etfs = read_prices(conn, "etf_prices")
    if signals.empty or etfs.empty:
        return None
    return _run_cached_backtest(
        signals,
        etfs,
        config.signals.symbols,
        tuple(config.allocation.etf_weights.items()),
        config.zscore.window,
        config.zscore.min_periods,
        config.zscore.trigger_threshold,
        config.backtest.research_hold_weeks,
        config.backtest.forward_return_weeks,
    )


def _load_event_study(conn, config):
    signals = read_prices(conn, "signal_prices")
    etfs = read_prices(conn, "etf_prices")
    if signals.empty or etfs.empty:
        return None
    return _run_cached_event_study(
        signals,
        etfs,
        config.signals.symbols,
        tuple(config.allocation.etf_weights.items()),
        config.zscore.window,
        config.zscore.min_periods,
        config.backtest.zscore_thresholds,
        config.backtest.forward_return_weeks,
    )


def _signal_research(conn, config) -> None:
    st.header("Signal Research")
    result = _load_backtest(conn, config)
    if result is None or result.rankings.empty:
        _missing_data_panel(conn, config, "Signal research")
        return

    active = result.rankings[result.rankings["status"] == "active"]
    if not active.empty:
        best = active.iloc[0]
        st.metric("Best Active Signal", _signal_label(best["symbol"], config), f"Sharpe {best['sharpe']:.2f}" if pd.notna(best["sharpe"]) else "Sharpe n/a")

    st.dataframe(_format_percent_columns(_with_signal_description(result.rankings, config)), use_container_width=True, hide_index=True)

    event_study = _load_event_study(conn, config)
    if event_study is not None and not event_study.summary.empty:
        st.subheader("Z-Score Event Study")
        summary = _with_signal_description(event_study.summary, config)
        st.dataframe(_format_percent_columns(summary), use_container_width=True, hide_index=True)

        st.subheader("Latest Crossings")
        latest = event_study.events.head(50).copy()
        latest = _with_signal_description(latest, config)
        st.dataframe(_format_percent_columns(latest), use_container_width=True, hide_index=True)


def _signal_detail(conn, config) -> None:
    st.header("Signal Detail")
    result = _load_backtest(conn, config)
    if result is None or result.zscores.empty:
        _missing_data_panel(conn, config, "Signal detail")
        return

    default_index = list(config.signals.symbols).index(config.signals.default) if config.signals.default in config.signals.symbols else 0
    symbol = st.selectbox(
        "Signal",
        config.signals.symbols,
        index=default_index,
        format_func=lambda value: _signal_label(value, config),
    )
    signal = result.zscores[result.zscores["symbol"] == symbol].copy()
    if signal.empty:
        st.warning(f"No data loaded for {symbol}.")
        return

    signal = signal.sort_values("date")
    latest = signal.dropna(subset=["z_score"]).tail(1)
    if not latest.empty:
        row = latest.iloc[0]
        st.metric("Latest Z-Score", f"{row['z_score']:.2f}", f"Close {row['close']:.2f}")

    chart = signal.set_index("date")[["close", "rolling_mean"]].dropna(how="all")
    st.line_chart(chart)
    st.line_chart(signal.set_index("date")[["z_score"]].dropna())

    details = result.detail[result.detail["symbol"] == symbol].sort_values("signal_date", ascending=False)
    st.subheader("Trigger History")
    if details.empty:
        st.info("No triggers for this signal under the current z-score rule.")
    else:
        st.dataframe(_format_percent_columns(details), use_container_width=True, hide_index=True)


def _allocation_preview(conn, config) -> None:
    st.header("Allocation Preview")
    result = _load_backtest(conn, config)
    if result is None or result.rankings.empty or result.zscores.empty:
        _missing_data_panel(conn, config, "Allocation preview")
        return

    active = result.rankings[result.rankings["status"] == "active"]
    default_symbol = active.iloc[0]["symbol"] if not active.empty else config.signals.default
    symbol = st.selectbox(
        "Signal for allocation",
        config.signals.symbols,
        index=list(config.signals.symbols).index(default_symbol),
        format_func=lambda value: _signal_label(value, config),
    )
    cash = st.number_input("Available cash to deploy", min_value=0.0, value=config.allocation.default_cash, step=500.0)

    signal = result.zscores[result.zscores["symbol"] == symbol].dropna(subset=["z_score"]).sort_values("date")
    if signal.empty:
        st.warning(f"No valid z-score history for {symbol}.")
        return

    latest = signal.iloc[-1]
    preview = allocation_preview(
        cash=cash,
        latest_z_score=float(latest["z_score"]),
        threshold=config.zscore.trigger_threshold,
        etf_weights=config.allocation.etf_weights,
        deploy_pct=config.allocation.trigger_deploy_pct,
    )
    active_trigger = bool(preview["trigger_active"].iloc[0])
    st.metric("Latest Z-Score", f"{latest['z_score']:.2f}", "Trigger active" if active_trigger else "No allocation")
    display = preview.copy()
    display["weight"] = display["weight"].map(lambda value: f"{value:.2%}")
    display["allocation_dollars"] = display["allocation_dollars"].map(lambda value: f"${value:,.2f}")
    st.dataframe(display, use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="TradingView Signal Research", layout="wide")
    config = load_config()
    conn = connect(config.database_path)
    _ensure_automated_data(conn, config)

    st.title("TradingView Signal Research")
    st.caption("Research breadth-signal z-scores before using them for manual broker allocation decisions.")

    page = st.sidebar.radio(
        "Page",
        ["Data", "Signal Research", "Signal Detail", "Allocation Preview"],
        index=1,
    )
    st.sidebar.write(f"Allocation: z-score < {config.zscore.trigger_threshold}")
    st.sidebar.write(f"Alerts: {', '.join(f'+/-{threshold:g}' for threshold in config.alerts.zscore_thresholds)}")
    st.sidebar.write(f"Window: {config.zscore.window} trading days")

    if page == "Data":
        _data_manager(conn, config)
    elif page == "Signal Research":
        _signal_research(conn, config)
    elif page == "Signal Detail":
        _signal_detail(conn, config)
    else:
        _allocation_preview(conn, config)
