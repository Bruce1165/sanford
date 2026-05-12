#!/usr/bin/env python3
import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT_DIR / "research" / "v4_trend_research" / "output"


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _to_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _env_int(name, default):
    return _to_int(os.environ.get(name, default), default)


def _env_float(name, default):
    return _to_float(os.environ.get(name, default), default)


def _read_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_csv_rows(path: Path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _clamp(v, low, high):
    return max(low, min(high, v))


def _latest_trade_dates(rows):
    dates = sorted({str(r.get("signal_date") or "")[:10] for r in rows if str(r.get("signal_date") or "").strip()})
    return [d for d in dates if d]


def _build_state_stats(rows, selected_dates):
    date_set = set(selected_dates)
    stats = {
        "S1_risk_on": {"n": 0, "s": 0, "dd_sum": 0.0},
        "S2_neutral": {"n": 0, "s": 0, "dd_sum": 0.0},
        "S3_risk_off": {"n": 0, "s": 0, "dd_sum": 0.0},
    }
    for r in rows:
        d = str(r.get("signal_date") or "")[:10]
        st = str(r.get("market_state") or "")
        if d not in date_set or st not in stats:
            continue
        ok_flag = _to_int(r.get("is_success_strict"), 0)
        dd = _to_float(r.get("drawdown_mag_t1_t8"), 0.0)
        stats[st]["n"] += 1
        stats[st]["s"] += 1 if ok_flag == 1 else 0
        stats[st]["dd_sum"] += dd
    for st in list(stats.keys()):
        n = stats[st]["n"]
        s = stats[st]["s"]
        dd_sum = stats[st]["dd_sum"]
        stats[st]["success_rate"] = (s / n) if n > 0 else 0.0
        stats[st]["avg_drawdown"] = (dd_sum / n) if n > 0 else 0.0
    return stats


def _adjust_floor_v11(state_name, base_floor, gate_floor, state_stats, policy):
    score_floor = float(base_floor)
    gate = int(gate_floor)
    n = _to_int(state_stats.get("n"), 0)
    success_rate = _to_float(state_stats.get("success_rate"), 0.0)
    avg_drawdown = _to_float(state_stats.get("avg_drawdown"), 0.0)

    min_n = _to_int(policy.get("min_n"), 20)
    target_sr = _to_float(policy.get("target_success_rate"), 0.25)
    target_dd = _to_float(policy.get("target_drawdown"), 0.055)
    max_abs_score_delta = _to_float(policy.get("max_abs_score_delta"), 0.15)
    reasons = []

    if n < min_n:
        reasons.append(f"insufficient_sample(n={n}<min_n={min_n}), keep")
        return round(score_floor, 3), int(_clamp(gate, 0, 3)), reasons

    sr_gap = target_sr - success_rate
    dd_gap = avg_drawdown - target_dd
    score_delta = 0.0
    gate_delta = 0

    if sr_gap > 0.06:
        score_delta += 0.12
        gate_delta += 1
        reasons.append(f"sr_gap={sr_gap:.4f}>0.06")
    elif sr_gap > 0.03:
        score_delta += 0.08
        gate_delta += 1
        reasons.append(f"sr_gap={sr_gap:.4f}>0.03")
    elif sr_gap > 0.015:
        score_delta += 0.05
        reasons.append(f"sr_gap={sr_gap:.4f}>0.015")
    elif sr_gap < -0.05:
        score_delta -= 0.06
        gate_delta -= 1
        reasons.append(f"sr_gap={sr_gap:.4f}<-0.05")
    elif sr_gap < -0.02:
        score_delta -= 0.03
        reasons.append(f"sr_gap={sr_gap:.4f}<-0.02")

    if dd_gap > 0.03:
        score_delta += 0.12
        gate_delta += 1
        reasons.append(f"dd_gap={dd_gap:.4f}>0.03")
    elif dd_gap > 0.015:
        score_delta += 0.08
        gate_delta += 1
        reasons.append(f"dd_gap={dd_gap:.4f}>0.015")
    elif dd_gap > 0.005:
        score_delta += 0.05
        reasons.append(f"dd_gap={dd_gap:.4f}>0.005")
    elif dd_gap < -0.02:
        score_delta -= 0.03
        reasons.append(f"dd_gap={dd_gap:.4f}<-0.02")

    score_delta = _clamp(score_delta, -max_abs_score_delta, max_abs_score_delta)
    score_floor = round(_clamp(score_floor + score_delta, 0.0, 3.0), 3)
    gate = int(_clamp(gate + gate_delta, 0, 3))
    if not reasons:
        reasons.append(f"{state_name}:near_target,keep")
    return score_floor, gate, reasons


def main():
    parser = argparse.ArgumentParser(description="V4.2 minimal daily retrain script")
    parser.add_argument("--as-of", default="auto", help="YYYY-MM-DD or auto")
    parser.add_argument("--window-days", type=int, default=60, help="lookback trade dates")
    parser.add_argument("--s1-min-n", type=int, default=None, help="override S1 min sample")
    parser.add_argument("--s1-target-sr", type=float, default=None, help="override S1 target success rate")
    parser.add_argument("--s1-target-dd", type=float, default=None, help="override S1 target drawdown")
    parser.add_argument("--s3-min-n", type=int, default=None, help="override S3 min sample")
    parser.add_argument("--s3-target-sr", type=float, default=None, help="override S3 target success rate")
    parser.add_argument("--s3-target-dd", type=float, default=None, help="override S3 target drawdown")
    parser.add_argument("--max-abs-score-delta", type=float, default=None, help="override max abs score delta")
    args = parser.parse_args()

    candidate_latest = OUTPUT_DIR / "v4_2_dynamic_candidate_latest.json"
    hardened_latest = OUTPUT_DIR / "v4_2_dynamic_hardened_candidate_latest.json"
    replay_pool_csv = OUTPUT_DIR / "v4_2_replay_daily_pool.csv"
    if not candidate_latest.exists() or not hardened_latest.exists():
        raise SystemExit("missing latest candidate/hardened snapshot")

    candidate = _read_json(candidate_latest)
    hardened = _read_json(hardened_latest)
    rows = _read_csv_rows(replay_pool_csv)
    all_dates = _latest_trade_dates(rows)
    if not all_dates:
        raise SystemExit("no replay daily pool dates available")

    as_of = all_dates[-1] if args.as_of == "auto" else str(args.as_of)[:10]
    eligible_dates = [d for d in all_dates if d <= as_of]
    if not eligible_dates:
        raise SystemExit(f"no eligible replay dates for as-of={as_of}")
    selected_dates = eligible_dates[-max(5, int(args.window_days)) :]
    stats = _build_state_stats(rows, selected_dates)

    hardening = hardened.get("hardening") if isinstance(hardened.get("hardening"), dict) else {}
    profile = hardening.get("profile") if isinstance(hardening.get("profile"), dict) else {}
    guards = hardening.get("state_quality_guards") if isinstance(hardening.get("state_quality_guards"), dict) else {}

    max_delta = (
        _to_float(args.max_abs_score_delta, 0.0)
        if args.max_abs_score_delta is not None
        else _env_float("V4_RETRAIN_V11_MAX_ABS_SCORE_DELTA", 0.15)
    )
    thresholds = {
        "S1_risk_on": {
            "min_n": int(args.s1_min_n) if args.s1_min_n is not None else _env_int("V4_RETRAIN_V11_S1_MIN_N", 25),
            "target_success_rate": (
                float(args.s1_target_sr)
                if args.s1_target_sr is not None
                else _env_float("V4_RETRAIN_V11_S1_TARGET_SUCCESS_RATE", 0.30)
            ),
            "target_drawdown": (
                float(args.s1_target_dd)
                if args.s1_target_dd is not None
                else _env_float("V4_RETRAIN_V11_S1_TARGET_DRAWDOWN", 0.055)
            ),
            "max_abs_score_delta": max_delta,
        },
        "S3_risk_off": {
            "min_n": int(args.s3_min_n) if args.s3_min_n is not None else _env_int("V4_RETRAIN_V11_S3_MIN_N", 20),
            "target_success_rate": (
                float(args.s3_target_sr)
                if args.s3_target_sr is not None
                else _env_float("V4_RETRAIN_V11_S3_TARGET_SUCCESS_RATE", 0.24)
            ),
            "target_drawdown": (
                float(args.s3_target_dd)
                if args.s3_target_dd is not None
                else _env_float("V4_RETRAIN_V11_S3_TARGET_DRAWDOWN", 0.060)
            ),
            "max_abs_score_delta": max_delta,
        },
    }

    s1 = stats.get("S1_risk_on") or {}
    s3 = stats.get("S3_risk_off") or {}
    s1_floor, s1_gate, s1_reasons = _adjust_floor_v11(
        "S1_risk_on",
        _to_float(profile.get("s1_score_floor"), 1.5),
        _to_int(profile.get("s1_gate_floor"), 0),
        s1,
        thresholds["S1_risk_on"],
    )
    s3_floor, s3_gate, s3_reasons = _adjust_floor_v11(
        "S3_risk_off",
        _to_float(profile.get("s3_score_floor"), 0.0),
        _to_int(profile.get("s3_gate_floor"), 0),
        s3,
        thresholds["S3_risk_off"],
    )

    profile["s1_score_floor"] = s1_floor
    profile["s1_gate_floor"] = s1_gate
    profile["s3_score_floor"] = s3_floor
    profile["s3_gate_floor"] = s3_gate
    guards.setdefault("S1_risk_on", {})
    guards.setdefault("S2_neutral", {})
    guards.setdefault("S3_risk_off", {})
    guards["S1_risk_on"]["dynamic_score_floor"] = s1_floor
    guards["S1_risk_on"]["gate_count_floor"] = s1_gate
    guards["S3_risk_off"]["dynamic_score_floor"] = s3_floor
    guards["S3_risk_off"]["gate_count_floor"] = s3_gate

    ts = datetime.now()
    ts_str = ts.strftime("%Y%m%d-%H%M%S")
    ts_iso = ts.isoformat()
    candidate_version = f"v4.2-dynamic-candidate-{ts_str}"
    hardened_version = f"v4.2-dynamic-hardened-{ts_str}"

    candidate["candidate_version"] = candidate_version
    candidate["published_at"] = ts_iso
    candidate["retrain_meta"] = {
        "method": "minimal_daily_reestimate_v1_1",
        "as_of": as_of,
        "window_dates": [selected_dates[0], selected_dates[-1]],
        "state_stats": stats,
        "thresholds": thresholds,
        "adjust_reasons": {
            "S1_risk_on": s1_reasons,
            "S3_risk_off": s3_reasons,
        },
    }

    hardened["candidate_version"] = hardened_version
    hardened["published_at"] = ts_iso
    hardened["base_candidate_version"] = candidate_version
    hardened.setdefault("hardening", {})
    hardened["hardening"]["profile"] = profile
    hardened["hardening"]["state_quality_guards"] = guards
    hardened["hardening"]["retrain_meta"] = {
        "method": "minimal_daily_reestimate_v1_1",
        "as_of": as_of,
        "window_dates": [selected_dates[0], selected_dates[-1]],
        "state_stats": stats,
        "thresholds": thresholds,
        "adjust_reasons": {
            "S1_risk_on": s1_reasons,
            "S3_risk_off": s3_reasons,
        },
    }

    candidate_versioned = OUTPUT_DIR / f"v4_2_dynamic_candidate_{ts_str}.json"
    hardened_versioned = OUTPUT_DIR / f"v4_2_dynamic_hardened_candidate_{ts_str}.json"
    _write_json(candidate_versioned, candidate)
    _write_json(hardened_versioned, hardened)
    _write_json(candidate_latest, candidate)
    _write_json(hardened_latest, hardened)

    print(f"[retrain] as_of={as_of} dates={selected_dates[0]}..{selected_dates[-1]} n={len(selected_dates)}")
    print(f"[retrain] S1 floor={s1_floor} gate={s1_gate} | S3 floor={s3_floor} gate={s3_gate}")
    print(f"[retrain] candidate={candidate_version}")
    print(f"[retrain] hardened={hardened_version}")


if __name__ == "__main__":
    main()
