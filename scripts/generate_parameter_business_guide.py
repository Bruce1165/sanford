#!/usr/bin/env python3
"""Generate a user-readable business guide for all configurable screener parameters."""

from __future__ import annotations

import json
from pathlib import Path


def _fmt_range(meta: dict) -> str:
    mn = meta.get("min")
    mx = meta.get("max")
    if mn is not None and mx is not None:
        return f"{mn} ~ {mx}"
    if mn is not None:
        return f">= {mn}"
    if mx is not None:
        return f"<= {mx}"
    return "不限"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    cfg_dir = repo_root / "config" / "screeners"
    out_file = (
        repo_root
        / "TECHNICAL_DOCS"
        / "components"
        / "screening"
        / "all_config_parameter_business_guide.md"
    )

    lines: list[str] = []
    lines.append("# 全系统可配置参数业务语义清单")
    lines.append("")
    lines.append("- 来源：`config/screeners/*.json`。")
    lines.append("- 说明：每个参数都用业务语言解释“它控制什么”。")
    lines.append("")

    for cfg_file in sorted(cfg_dir.glob("*.json")):
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        screener_name = cfg_file.stem
        display_name = data.get("display_name", screener_name)
        params = data.get("parameters", {})

        lines.append(f"## {screener_name}（{display_name}）")
        if not isinstance(params, dict) or not params:
            lines.append("- 当前无可配置参数。")
            lines.append("")
            continue

        for param_name, meta in params.items():
            if not isinstance(meta, dict):
                continue
            current = meta.get("value", "-")
            default = meta.get("default", "-")
            desc = str(meta.get("description", "")).strip() or "（待补充）"
            lines.append(
                f"- `{param_name}`（当前{current}，默认{default}，范围{_fmt_range(meta)}）=> {desc}"
            )
        lines.append("")

    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
