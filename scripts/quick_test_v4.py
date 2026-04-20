#!/usr/bin/env python3
"""
快速测试V4筛选器 - 只处理前10只股票
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'screeners'))

from coffee_cup_screener_v4 import CoffeeCupScreenerV4
import logging

# 配置日志（显示详细过程）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def quick_test():
    """快速测试V4筛选器"""
    print("="*60)
    print("咖啡杯形态筛选器 V4 - 快速测试")
    print("="*60)

    screener = CoffeeCupScreenerV4()

    # 获取前10只股票
    stocks = screener.get_all_stocks()[:10]
    print(f"\n测试股票数量: {len(stocks)}")

    # ========== 输出时间跨度参数 ==========
    print(f"\n{'='*60}")
    print("时间跨度参数（用于计算需要查询的数据天数）：")
    print(f"{'='*60}")

    # 计算需要的数据天数
    required_days = screener.calculate_required_days()

    # 各组成部分的最大周期
    print(f"\n形态组成部分及其最大时间周期：")
    print(f"  • 左杯沿形成（预估）: 10天")
    print(f"  • 快速下调期（最大）: {screener.params.RAPID_DECLINE_MAX}天")
    print(f"  • 杯底震荡期（最大）: {screener.params.BOTTOM_OSCILLATE_MAX}天")
    print(f"  • 温和上涨-震荡期（最大）: {screener.params.ASCENT_OSCILLATE_MAX}天")
    print(f"  • 温和上涨-快速上涨期（最大）: {screener.params.ASCENT_RAPID_MAX}天")
    print(f"  • 杯柄期（最大）: {screener.params.HANDLE_PERIOD_MAX}天")
    print(f"  • 缓冲天数: 20天")

    print(f"\n{'-'*60}")
    print(f"✓ 动态计算需要的历史数据天数: {required_days}天")
    print(f"✓ 实际查询天数（含20%缓冲）: {int(required_days * 1.2)}天")
    print(f"{'='*60}\n")

    # 输出其他参数
    print(f"\n其他参数配置：")
    print(f"  两个杯沿价格匹配度: ±{screener.params.RIM_PRICE_MATCH_PCT*100:.0f}%")
    print(f"  杯深范围: {screener.params.CUP_DEPTH_MIN*100:.0f}%-{screener.params.CUP_DEPTH_MAX*100:.0f}%")
    print(f"  杯柄下跌限制: ≤杯深的{screener.params.HANDLE_MAX_DROP_PCT*100:.0f}%")
    print(f"  成交量对比天数: {screener.params.VOLUME_COMPARISON_DAYS}天")
    print(f"  成交量倍数要求: ≥{screener.params.VOLUME_RATIO_THRESHOLD}倍")
    print(f"  最小换手率: {screener.params.MIN_TURNOVER}%")
    print(f"  最小涨幅: {screener.params.MIN_PCT_CHANGE}%")

    print(f"\n{'='*60}")
    print("开始筛选过程...")
    print(f"{'='*60}\n")

    results = []
    errors = 0
    passed_turnover = 0
    passed_pct_change = 0
    passed_pattern = 0

    for i, stock in enumerate(stocks, 1):
        print(f"\n[{i}/{len(stocks)}] {stock.code} - {stock.name}")
        print(f"  步骤1: 获取历史数据（{int(required_days * 1.2)}天）")
        try:
            result = screener.screen_stock(stock.code, stock.name)
            if result:
                results.append(result)
                passed_pattern += 1
                print(f"  ✓ 通过所有筛选！")
                print(f"    └─ 杯深: {result['cup_depth_pct']}% | 杯沿间隔: {result['rim_interval_days']}天")
                print(f"    └─ 震荡期: {result['oscillate_days']}天 | 快速上涨: {result['rapid_ascent_days']}天")
                print(f"    └─ 杯柄: {result['handle_days']}天 | 杯柄下跌: {result['handle_drop_pct']}%")
                print(f"    └─ 成交量倍数: {result['volume_ratio']}倍")
            # 注意：筛选步骤详细信息会从日志输出显示
        except Exception as e:
            errors += 1
            print(f"  ✗ 错误: {e}")

    print("\n" + "="*60)
    print(f"测试完成!")
    print(f"  处理股票: {len(stocks)} 只")
    print(f"  找到形态: {len(results)} 只")
    print(f"  处理错误: {errors} 只")
    print(f"  通过换手率: {passed_turnover} 只")
    print(f"  通过涨幅: {passed_pct_change} 只")
    print(f"  通过形态: {passed_pattern} 只")
    print("="*60)

    if results:
        print(f"\n✓ 符合条件的股票：")
        for r in results:
            print(f"\n  {r['code']} - {r['name']}")
            print(f"    收盘价: {r['close']} | 换手率: {r['turnover']}% | 涨幅: {r['pct_change']}%")
            print(f"    左杯沿: {r['left_rim_date']} ({r['left_rim_price']})")
            print(f"    右杯沿: {r['right_rim_date']} ({r['right_rim_price']})")
            print(f"    杯底: {r['cup_bottom_price']} | 杯深: {r['cup_depth_pct']}% | 间隔: {r['rim_interval_days']}天")
            print(f"    形态结构: 震荡{r['oscillate_days']}天 + 快速上涨{r['rapid_ascent_days']}天 + 杯柄{r['handle_days']}天")

    return results

if __name__ == '__main__':
    quick_test()
