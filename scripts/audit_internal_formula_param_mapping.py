#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path("/Users/mac/NeoTrade2")
CFG_DIR = ROOT / "config" / "screeners"
SCR_DIR = ROOT / "screeners"

SCREENERS = {
    "coffee_cup_v4": "coffee_cup_handle_screener_v4.py",
    "daily_hot_cold": "daily_hot_cold_screener.py",
    "er_ban_hui_tiao": "er_ban_hui_tiao_screener.py",
    "jin_feng_huang": "jin_feng_huang_screener.py",
    "shi_pan_xian": "shi_pan_xian_screener.py",
    "yin_feng_huang": "yin_feng_huang_screener.py",
    "zhang_ting_bei_liang_yin": "zhang_ting_bei_liang_yin_screener.py",
}

# Keep consistent with backend/screeners.py
LEGACY_ALIAS_MAPPING = {
    "RAPID_DECLINE_DAYS": "rapid_decline_days",
    "RAPID_ASCENT_DAYS": "rapid_ascent_days",
    "HANDLE_MAX_DAYS": "handle_max_days",
    "AMOUNT_RATIO_THRESHOLD": "amount_ratio_threshold",
    "OSCILLATION_PRICE_CEIL_PCT": "oscillation_price_ceil_pct",
}


def first_screener_class(tree: ast.AST) -> ast.ClassDef | None:
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and "Screener" in node.name:
            return node
    return None


def get_init_args(cls: ast.ClassDef) -> tuple[list[str], ast.FunctionDef | None]:
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            args = [a.arg for a in node.args.args if a.arg != "self"]
            return args, node
    return [], None


def get_self_loads_outside_init(cls: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for fn in cls.body:
        if isinstance(fn, ast.FunctionDef) and fn.name != "__init__":
            for node in ast.walk(fn):
                if not isinstance(node, ast.Attribute):
                    continue
                if not isinstance(node.ctx, ast.Load):
                    continue
                if isinstance(node.value, ast.Name) and node.value.id == "self":
                    names.add(node.attr)
    return names


def get_self_params_loads_outside_init(cls: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for fn in cls.body:
        if isinstance(fn, ast.FunctionDef) and fn.name != "__init__":
            for node in ast.walk(fn):
                if not isinstance(node, ast.Attribute):
                    continue
                if not isinstance(node.ctx, ast.Load):
                    continue
                base = node.value
                if (
                    isinstance(base, ast.Attribute)
                    and isinstance(base.value, ast.Name)
                    and base.value.id == "self"
                    and base.attr == "params"
                ):
                    names.add(node.attr)
    return names


def audit_one(screener_name: str, py_file: str) -> dict:
    config = json.loads((CFG_DIR / f"{screener_name}.json").read_text())
    cfg_keys = list(config.get("parameters", {}).keys())

    tree = ast.parse((SCR_DIR / py_file).read_text())
    cls = first_screener_class(tree)
    if cls is None:
        return {
            "error": "Screener class not found",
            "config_params": len(cfg_keys),
        }

    init_arg_names, _ = get_init_args(cls)
    init_arg_set = set(init_arg_names)

    mapping_missing: list[str] = []
    mapped_param: dict[str, str | None] = {}
    for key in cfg_keys:
        candidates: list[str] = []
        alias_name = LEGACY_ALIAS_MAPPING.get(key)
        if alias_name:
            candidates.append(alias_name)
        auto_name = key.lower()
        if auto_name not in candidates:
            candidates.append(auto_name)
        hit = next((c for c in candidates if c in init_arg_set), None)
        mapped_param[key] = hit
        if not hit:
            mapping_missing.append(key)

    if screener_name == "coffee_cup_v4":
        loads = get_self_params_loads_outside_init(cls)
        usage_missing = [k for k in cfg_keys if k not in loads]
        usage_mode = "self.params.<CONFIG_KEY>"
    else:
        loads = get_self_loads_outside_init(cls)
        usage_missing = []
        for key in cfg_keys:
            p = mapped_param.get(key)
            if p and p not in loads:
                usage_missing.append(key)
        usage_mode = "self.<mapped_param>"

    return {
        "config_params": len(cfg_keys),
        "mapped_ok": len(cfg_keys) - len(mapping_missing),
        "mapping_missing": mapping_missing,
        "usage_mode": usage_mode,
        "used_ok": len(cfg_keys) - len(usage_missing),
        "usage_missing": usage_missing,
    }


def main() -> None:
    report = {name: audit_one(name, py_file) for name, py_file in SCREENERS.items()}
    print(json.dumps(report, ensure_ascii=False, indent=2))

    all_mapping_missing = [
        (name, key)
        for name, result in report.items()
        for key in result.get("mapping_missing", [])
    ]
    all_usage_missing = [
        (name, key)
        for name, result in report.items()
        for key in result.get("usage_missing", [])
    ]
    print("\nSUMMARY")
    print(f"mapping_missing_total={len(all_mapping_missing)}")
    print(f"usage_missing_total={len(all_usage_missing)}")
    if all_mapping_missing:
        print(f"mapping_missing_items={all_mapping_missing}")
    if all_usage_missing:
        print(f"usage_missing_items={all_usage_missing}")


if __name__ == "__main__":
    main()
