from datetime import datetime, timezone

from tradingview_signal_dashboard.schedule_guard import should_run_for_event


def test_schedule_guard_allows_10am_eastern_during_daylight_time():
    assert should_run_for_event("schedule", datetime(2026, 7, 1, 14, 0, tzinfo=timezone.utc))


def test_schedule_guard_allows_10am_eastern_during_standard_time():
    assert should_run_for_event("schedule", datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc))


def test_schedule_guard_blocks_wrong_eastern_hour():
    assert not should_run_for_event("schedule", datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc))


def test_schedule_guard_manual_runs_bypass_time_check():
    assert should_run_for_event("workflow_dispatch", datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc))
