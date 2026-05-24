from __future__ import annotations

import pandas as pd

from tradingview_signal_dashboard.indicators import is_allocation_trigger


def allocation_preview(
    cash: float,
    latest_z_score: float,
    threshold: float,
    etf_weights: dict[str, float],
    deploy_pct: float = 1.0,
) -> pd.DataFrame:
    should_deploy = is_allocation_trigger(latest_z_score, threshold)
    deploy_amount = float(cash) * float(deploy_pct) if should_deploy else 0.0
    total_weight = sum(etf_weights.values())
    if total_weight <= 0:
        raise ValueError("ETF weights must sum to a positive number")

    rows = []
    for symbol, weight in etf_weights.items():
        normalized_weight = float(weight) / total_weight
        rows.append(
            {
                "symbol": symbol,
                "weight": normalized_weight,
                "allocation_dollars": deploy_amount * normalized_weight,
                "trigger_active": should_deploy,
            }
        )
    return pd.DataFrame(rows)
