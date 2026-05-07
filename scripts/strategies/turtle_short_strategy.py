#!/usr/bin/env python3
"""
Reusable turtle short strategy core for Neil pool.

Scope in current phase:
- Config loading + validation
- Signal calculation on OHLC dataframe
- Optional DB data loader for single stock
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "screeners" / "turtle_short_neil.json"


@dataclass(frozen=True)
class TurtleShortConfig:
    entry_n: int
    exit_n: int
    new_entry_rule: str
    param_version: str
    raw_doc: dict


def _read_json(path: Path) -> dict:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"invalid config json format: {path}")
    return loaded


def _extract_int_param(doc: dict, key: str) -> int:
    param = (doc.get("parameters") or {}).get(key) or {}
    value = param.get("value", param.get("default"))
    if value is None:
        raise ValueError(f"missing required parameter: {key}")
    try:
        return int(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid int parameter {key}: {value}") from exc


def _extract_str_param(doc: dict, key: str) -> str:
    param = (doc.get("parameters") or {}).get(key) or {}
    value = param.get("value", param.get("default"))
    if value is None:
        raise ValueError(f"missing required parameter: {key}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"invalid empty parameter: {key}")
    return text


def load_turtle_short_config(config_path: Optional[str] = None) -> TurtleShortConfig:
    path = Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"turtle config not found: {path}")

    doc = _read_json(path)
    entry_n = _extract_int_param(doc, "ENTRY_N")
    exit_n = _extract_int_param(doc, "EXIT_N")
    new_entry_rule = _extract_str_param(doc, "NEW_ENTRY_RULE")
    if new_entry_rule != "today_true_prev_false":
        raise ValueError(f"unsupported NEW_ENTRY_RULE: {new_entry_rule}")
    if not (5 <= entry_n <= 120):
        raise ValueError(f"ENTRY_N out of range: {entry_n}")
    if not (2 <= exit_n <= 60):
        raise ValueError(f"EXIT_N out of range: {exit_n}")
    if entry_n <= exit_n:
        raise ValueError(f"ENTRY_N must be greater than EXIT_N, got {entry_n}/{exit_n}")

    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    version = str(metadata.get("version") or "").strip()
    if not version:
        digest_source = json.dumps(
            {"entry_n": entry_n, "exit_n": exit_n, "new_entry_rule": new_entry_rule},
            sort_keys=True,
            ensure_ascii=False,
        )
        version = f"sha1:{hashlib.sha1(digest_source.encode('utf-8')).hexdigest()[:12]}"

    return TurtleShortConfig(
        entry_n=entry_n,
        exit_n=exit_n,
        new_entry_rule=new_entry_rule,
        param_version=version,
        raw_doc=doc,
    )


def load_daily_prices_for_stock(
    db_path: str,
    stock_code: str,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load daily OHLC prices for one stock, ordered by trade_date ascending.
    """
    sql = """
        SELECT code, trade_date, open, high, low, close, volume, amount, turnover, pct_change
        FROM daily_prices
        WHERE code = ?
    """
    params: list = [stock_code]
    if end_date:
        sql += " AND trade_date <= ?"
        params.append(end_date)
    sql += " ORDER BY trade_date ASC"

    conn = sqlite3.connect(db_path, timeout=30)
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()
    return df


def compute_turtle_short_signals(df: pd.DataFrame, config: TurtleShortConfig) -> pd.DataFrame:
    """
    Compute turtle short signals.

    Core rule:
    - entry_level: highest high of previous ENTRY_N bars (exclude today)
    - exit_level: lowest low of previous EXIT_N bars (exclude today)
    - is_entry: close > entry_level
    - is_exit: close < exit_level
    - is_new_entry: is_entry is true today and false yesterday
    """
    required_cols = {"trade_date", "high", "low", "close"}
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    out = df.copy()
    out = out.sort_values("trade_date").reset_index(drop=True)
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")

    out["entry_level"] = out["high"].shift(1).rolling(window=config.entry_n, min_periods=config.entry_n).max()
    out["exit_level"] = out["low"].shift(1).rolling(window=config.exit_n, min_periods=config.exit_n).min()

    out["is_entry"] = (out["close"] > out["entry_level"]).fillna(False)
    out["is_exit"] = (out["close"] < out["exit_level"]).fillna(False)
    prev_entry = out["is_entry"].shift(1, fill_value=False).astype(bool)
    out["is_new_entry"] = out["is_entry"].astype(bool) & (~prev_entry)

    out["param_version"] = config.param_version
    out["entry_n"] = int(config.entry_n)
    out["exit_n"] = int(config.exit_n)

    return out
