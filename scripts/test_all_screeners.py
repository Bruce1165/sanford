#!/usr/bin/env python3
"""
test_all_screeners.py — NeoTrade Screener API 集成测试

用法（在 Mac 上运行）：
    python3 /Users/mac/NeoTrade2/scripts/test_all_screeners.py

依赖：requests（pip install requests）
"""

import sys
import json
import time
import requests
from datetime import datetime

# ── 配置 ──────────────────────────────────────────────────────
BASE_URL   = "http://localhost:8765"   # 如果端口不同请修改
TIMEOUT    = 120                        # 单个 screener 超时秒数
TODAY      = datetime.now().strftime("%Y-%m-%d")

SCREENERS = [
    "ascending_triangle_screener",
    "ashare_21_screener",
    "breakout_20day_screener",
    "breakout_main_screener",
    "coffee_cup_screener",
    "daily_hot_cold_screener",
    "double_bottom_screener",
    "er_ban_hui_tiao_screener",
    "flat_base_screener",
    "high_tight_flag_screener",
    "jin_feng_huang_screener",
    "shi_pan_xian_screener",
    "shuang_shou_ban_screener",
    "yin_feng_huang_screener",
    "zhang_ting_bei_liang_yin_screener",
]

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

# ── 辅助 ──────────────────────────────────────────────────────
def check_flask_alive():
    try:
        r = requests.get(f"{BASE_URL}/api/screeners", timeout=5)
        return r.status_code < 500
    except Exception:
        return False


def run_screener(name: str) -> dict:
    """调用 /api/screener/<name>/run，返回结果摘要"""
    url = f"{BASE_URL}/api/screener/{name}/run"
    try:
        t0 = time.time()
        resp = requests.post(url, json={"date": TODAY}, timeout=TIMEOUT)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}", "elapsed": elapsed}

        data = resp.json()

        # 兼容不同返回格式
        results = data.get("results") or data.get("data") or []
        if isinstance(results, dict):               # daily_hot_cold: {hot:[...], cold:[...]}
            count = sum(len(v) for v in results.values() if isinstance(v, list))
        elif isinstance(results, list):
            count = len(results)
        else:
            count = 0

        # 检查是否有 STATUS 污染
        status_leak = False
        if isinstance(results, list):
            status_leak = any(r.get("code") == "STATUS" for r in results if isinstance(r, dict))

        return {
            "ok": True,
            "count": count,
            "elapsed": elapsed,
            "status_leak": status_leak,
            "raw_keys": list(data.keys()),
        }

    except requests.exceptions.Timeout:
        return {"ok": False, "error": f"超时（>{TIMEOUT}s）", "elapsed": TIMEOUT}
    except Exception as e:
        return {"ok": False, "error": str(e), "elapsed": 0}


# ── 主程序 ────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print(f"  NeoTrade Screener API 集成测试  [{TODAY}]")
    print(f"  Target: {BASE_URL}")
    print("=" * 65)

    # 先检查 Flask 是否存活
    if not check_flask_alive():
        print(f"\n{FAIL} Flask 服务未响应 ({BASE_URL})")
        print("    请先重启 Flask：")
        print("    sudo pkill -9 -f 'python3.*app.py'")
        print("    sudo launchctl start com.neotrade.flask")
        sys.exit(1)

    print(f"✅ Flask 服务在线\n")

    pass_count = 0
    fail_count = 0
    warn_count = 0
    summary_rows = []

    for name in SCREENERS:
        sys.stdout.write(f"  运行 {name} ... ")
        sys.stdout.flush()

        res = run_screener(name)

        if not res["ok"]:
            status = FAIL
            detail = res["error"]
            fail_count += 1
        elif res.get("status_leak"):
            status = WARN
            detail = f"返回 {res['count']} 条，但含 STATUS 污染！"
            warn_count += 1
        else:
            status = PASS
            detail = f"{res['count']} 条结果  ({res['elapsed']:.1f}s)"
            pass_count += 1

        print(f"{status}  {detail}")
        summary_rows.append((name, status, detail))

    # ── 汇总 ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"  总计: {pass_count} 通过  {warn_count} 警告  {fail_count} 失败")
    print("=" * 65)

    if fail_count == 0 and warn_count == 0:
        print("🎉 所有 screener 正常返回数据，无 STATUS 污染！")
    elif fail_count == 0:
        print(f"⚠️  有 {warn_count} 个 screener 存在问题，请检查上方警告。")
    else:
        print(f"❌ 有 {fail_count} 个 screener 失败，请检查 Flask 日志。")
        print(f"   tail -50 ~/neotrade_flask.log | grep -i ERROR")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
