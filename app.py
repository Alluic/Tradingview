from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path


def _running_inside_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except Exception:
        return False
    return get_script_run_ctx(suppress_warning=True) is not None


if __name__ == "__main__":
    if not _running_inside_streamlit():
        script_path = Path(__file__).resolve()
        env = os.environ.copy()
        env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
        env.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
        env.setdefault("STREAMLIT_SERVER_SHOW_EMAIL_PROMPT", "false")
        raise SystemExit(
            subprocess.call(
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    str(script_path),
                    "--server.headless=true",
                    "--server.showEmailPrompt=false",
                    "--browser.gatherUsageStats=false",
                    *sys.argv[1:],
                ],
                env=env,
            )
        )

    from tradingview_signal_dashboard.app import main

    main()
