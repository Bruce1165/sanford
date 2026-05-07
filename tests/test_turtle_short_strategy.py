#!/usr/bin/env python3
"""Unit tests for turtle short strategy core."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.strategies.turtle_short_strategy import (  # noqa: E402
    compute_turtle_short_signals,
    load_turtle_short_config,
)


def _build_df_for_entry_and_exit() -> pd.DataFrame:
    # 30 trading days, crafted to produce one new entry then one exit.
    rows = []
    for i in range(1, 31):
        # Base range
        high = 100 + (i % 3)
        low = 95 + (i % 2)
        close = 98 + (i % 2)

        # Day 22: breakout above previous 20-day highs
        if i == 22:
            high = 130
            low = 110
            close = 125

        # Day 26: drop below previous 10-day lows -> exit
        if i == 26:
            high = 95
            low = 80
            close = 82

        rows.append(
            {
                "trade_date": f"2026-01-{i:02d}",
                "high": float(high),
                "low": float(low),
                "close": float(close),
            }
        )
    return pd.DataFrame(rows)


def test_load_turtle_short_default_config():
    cfg = load_turtle_short_config()
    assert cfg.entry_n == 20
    assert cfg.exit_n == 10
    assert cfg.new_entry_rule == "today_true_prev_false"
    assert cfg.param_version


def test_compute_new_entry_occurs_once_on_breakout():
    cfg = load_turtle_short_config()
    df = _build_df_for_entry_and_exit()
    out = compute_turtle_short_signals(df, cfg)

    new_entry_days = out.loc[out["is_new_entry"] == True, "trade_date"].dt.strftime("%Y-%m-%d").tolist()  # noqa: E712
    assert len(new_entry_days) == 1
    assert new_entry_days[0] == "2026-01-22"


def test_compute_exit_triggered_on_breakdown():
    cfg = load_turtle_short_config()
    df = _build_df_for_entry_and_exit()
    out = compute_turtle_short_signals(df, cfg)

    exit_days = out.loc[out["is_exit"] == True, "trade_date"].dt.strftime("%Y-%m-%d").tolist()  # noqa: E712
    assert "2026-01-26" in exit_days
