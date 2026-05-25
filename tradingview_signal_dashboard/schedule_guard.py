from __future__ import annotations

from datetime import datetime, timezone
import os
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")


def should_run_for_event(
    event_name: str,
    now_utc: datetime | None = None,
    target_hour: int = 10,
    target_minute: int = 0,
) -> bool:
    if event_name != "schedule":
        return True

    current = now_utc or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local = current.astimezone(EASTERN)
    return local.weekday() < 5 and local.hour == target_hour and local.minute == target_minute


def main() -> int:
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    should_run = should_run_for_event(event_name)
    value = "true" if should_run else "false"
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"should_run={value}\n")
    print(f"10 AM Eastern schedule guard: should_run={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
