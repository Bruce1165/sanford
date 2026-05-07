#!/usr/bin/env python3
"""
Reusable triple-screen strategy core for Neil pipeline.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "screeners" / "triple_screen_neil.json"


@dataclass(frozen=True)
class TripleScreenConfig:
    timing_rsi_threshold: float
    entry_lookback_days: int
    stop_lookback_days: int
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


def _extract_float_param(doc: dict, key: str) -> float:
    param = (doc.get("parameters") or {}).get(key) or {}
    value = param.get("value", param.get("default"))
    if value is None:
        raise ValueError(f"missing required parameter: {key}")
    try:
        return float(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid float parameter {key}: {value}") from exc


def _extract_str_param(doc: dict, key: str) -> str:
    param = (doc.get("parameters") or {}).get(key) or {}
    value = param.get("value", param.get("default"))
    if value is None:
        raise ValueError(f"missing required parameter: {key}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"invalid empty parameter: {key}")
    return text


def load_triple_screen_config(config_path: Optional[str] = None) -> TripleScreenConfig:
    path = Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"triple-screen config not found: {path}")

    doc = _read_json(path)
    timing_rsi_threshold = _extract_float_param(doc, "TIMING_RSI_THRESHOLD")
    entry_lookback_days = _extract_int_param(doc, "ENTRY_LOOKBACK_DAYS")
    stop_lookback_days = _extract_int_param(doc, "STOP_LOOKBACK_DAYS")
    new_entry_rule = _extract_str_param(doc, "NEW_ENTRY_RULE")

    if new_entry_rule != "today_true_prev_false":
        raise ValueError(f"unsupported NEW_ENTRY_RULE: {new_entry_rule}")
    if not (10.0 <= timing_rsi_threshold <= 60.0):
        raise ValueError(f"TIMING_RSI_THRESHOLD out of range: {timing_rsi_threshold}")
    if not (2 <= entry_lookback_days <= 30):
        raise ValueError(f"ENTRY_LOOKBACK_DAYS out of range: {entry_lookback_days}")
    if not (3 <= stop_lookback_days <= 60):
        raise ValueError(f"STOP_LOOKBACK_DAYS out of range: {stop_lookback_days}")
    if stop_lookback_days <= entry_lookback_days:
        raise ValueError(
            f"STOP_LOOKBACK_DAYS must be greater than ENTRY_LOOKBACK_DAYS, got "
            f"{stop_lookback_days}/{entry_lookback_days}"
        )

    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    version = str(metadata.get("version") or "").strip()
    if not version:
        digest_source = json.dumps(
            {
                "timing_rsi_threshold": timing_rsi_threshold,
                "entry_lookback_days": entry_lookback_days,
                "stop_lookback_days": stop_lookback_days,
                "new_entry_rule": new_entry_rule,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        version = f"sha1:{hashlib.sha1(digest_source.encode('utf-8')).hexdigest()[:12]}"

    return TripleScreenConfig(
        timing_rsi_threshold=timing_rsi_threshold,
        entry_lookback_days=entry_lookback_days,
        stop_lookback_days=stop_lookback_days,
        new_entry_rule=new_entry_rule,
        param_version=version,
        raw_doc=doc,
    )


def load_daily_prices_for_stock(db_path: str, stock_code: str, end_date: Optional[str] = None) -> pd.DataFrame:
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
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def _ema(values: list[float], span: int) -> list[float]:
    if span <= 0 or not values:
        return []
    alpha = 2.0 / (span + 1.0)
    out: list[float] = []
    ema_value = float(values[0])
    out.append(ema_value)
    for val in values[1:]:
        ema_value = alpha * float(val) + (1.0 - alpha) * ema_value
        out.append(ema_value)
    return out


def _macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    if not values:
        return None
    ema_fast = _ema(values, fast)
    ema_slow = _ema(values, slow)
    if len(ema_fast) != len(ema_slow):
        return None
    macd_line = [a - b for a, b in zip(ema_fast, ema_slow)]
    signal_line = _ema(macd_line, signal)
    hist = [m - s for m, s in zip(macd_line, signal_line)]
    return {"macd": macd_line, "signal": signal_line, "hist": hist}


def _rsi(values: list[float], period: int = 14) -> Optional[float]:
    if period <= 0 or len(values) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for idx in range(len(values) - period, len(values)):
        change = float(values[idx]) - float(values[idx - 1])
        if change >= 0:
            gains += change
        else:
            losses += -change
    avg_gain = gains / float(period)
    avg_loss = losses / float(period)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _weekly_macd_metrics(df: pd.DataFrame) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if df.empty:
        return None, None, None
    tmp = df.copy()
    tmp["trade_date"] = pd.to_datetime(tmp["trade_date"], errors="coerce")
    tmp = tmp.dropna(subset=["trade_date"])
    if tmp.empty:
        return None, None, None

    tmp["week_key"] = tmp["trade_date"].dt.strftime("%G-W%V")
    weekly = (
        tmp.groupby("week_key", as_index=False)
        .agg(
            trade_date=("trade_date", "max"),
            close=("close", "last"),
        )
        .sort_values("trade_date")
        .reset_index(drop=True)
    )
    if weekly.empty:
        return None, None, None
    macd = _macd([float(v) for v in weekly["close"].tolist()])
    if not macd:
        return None, None, None
    return macd["hist"][-1], macd["macd"][-1], macd["signal"][-1]


def compute_triple_screen_signals(df: pd.DataFrame, config: TripleScreenConfig) -> pd.DataFrame:
    required_cols = {"trade_date", "high", "low", "close"}
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    out = df.copy()
    out = out.sort_values("trade_date").reset_index(drop=True)
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    out = out.dropna(subset=["trade_date"]).reset_index(drop=True)

    out["entry_level"] = (
        out["high"]
        .shift(1)
        .rolling(window=config.entry_lookback_days, min_periods=config.entry_lookback_days)
        .max()
    )
    out["exit_level"] = (
        out["low"]
        .shift(1)
        .rolling(window=config.stop_lookback_days, min_periods=config.stop_lookback_days)
        .min()
    )
    out["entry_ok"] = (out["close"] > out["entry_level"]).fillna(False)
    out["is_exit_ref"] = (out["close"] < out["exit_level"]).fillna(False)

    rsi_values: list[Optional[float]] = []
    wk_hist_values: list[Optional[float]] = []
    wk_macd_values: list[Optional[float]] = []
    wk_sig_values: list[Optional[float]] = []
    trend_ok_values: list[bool] = []
    timing_ok_values: list[bool] = []

    for i in range(len(out)):
        window = out.iloc[: i + 1]
        close_list = [float(v) for v in window["close"].tolist()]
        rsi14 = _rsi(close_list, 14)
        wk_hist, wk_macd, wk_sig = _weekly_macd_metrics(window)
        trend_ok = (
            wk_hist is not None
            and wk_macd is not None
            and wk_sig is not None
            and float(wk_hist) > 0.0
            and float(wk_macd) > float(wk_sig)
        )
        timing_ok = bool(trend_ok and (rsi14 is not None) and (float(rsi14) < float(config.timing_rsi_threshold)))

        rsi_values.append(rsi14)
        wk_hist_values.append(wk_hist)
        wk_macd_values.append(wk_macd)
        wk_sig_values.append(wk_sig)
        trend_ok_values.append(bool(trend_ok))
        timing_ok_values.append(bool(timing_ok))

    out["rsi14"] = rsi_values
    out["weekly_macd_hist"] = wk_hist_values
    out["weekly_macd"] = wk_macd_values
    out["weekly_signal"] = wk_sig_values
    out["trend_ok"] = trend_ok_values
    out["timing_ok"] = timing_ok_values
    out["entry_ok"] = out["entry_ok"].astype(bool)

    composite_entry = out["trend_ok"].astype(bool) & out["timing_ok"].astype(bool) & out["entry_ok"].astype(bool)
    prev_composite = composite_entry.shift(1, fill_value=False).astype(bool)
    out["is_new_entry"] = composite_entry & (~prev_composite)
    out["is_entry"] = composite_entry

    out["param_version"] = config.param_version
    out["entry_lookback_days"] = int(config.entry_lookback_days)
    out["stop_lookback_days"] = int(config.stop_lookback_days)
    out["timing_rsi_threshold"] = float(config.timing_rsi_threshold)
    return out


def build_param_snapshot(config: TripleScreenConfig) -> str:
    payload = {
        "TIMING_RSI_THRESHOLD": float(config.timing_rsi_threshold),
        "ENTRY_LOOKBACK_DAYS": int(config.entry_lookback_days),
        "STOP_LOOKBACK_DAYS": int(config.stop_lookback_days),
        "NEW_ENTRY_RULE": str(config.new_entry_rule),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def normalize_trade_date(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return None
    return text[:10]
