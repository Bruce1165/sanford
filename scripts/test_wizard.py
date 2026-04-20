#!/usr/bin/env python3
"""
Quick Test for Coffee Cup Wizard - Verify basic logic
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from coffee_cup_wizard import CoffeeCupWizard
from datetime import datetime

def main():
    """Test wizard on a few stocks"""
    wizard = CoffeeCupWizard()

    print("=" * 60)
    print("Coffee Cup Wizard - Quick Test")
    print("=" * 60)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d')}")
    print()

    # Test on a few stocks with recent data
    test_stocks = [
        '600519',  # 贵州茅台 - 稳健
        '000001',  # 平安银行 - 大盘
        '300750',  # 宁波银行 - 小盘
        '601318',  # 中国平安 - 涨跌股
    ]

    print(f"Testing {len(test_stocks)} stocks...")
    print()

    for code in test_stocks:
        try:
            pred = wizard.analyze_stock(code)
            print(f"\n{'─' * 60}")
            print(f"股票代码: {code}")
            print(f"股票名称: {pred.name}")
            print(f" 代码: {pred.code}")
            print(f"完成度: {pred.completion_pct:.1f}%")
            print(f"预测概率: {pred.adjusted_probability:.1f}%")
            print(f"阶段: {pred.stage}")
            print(f"目标天数: {pred.target_days} 天")
            print(f"是否满足阈值: {'是' if pred.adjusted_probability >= 50 else '否'}")

            # Show component details
            print("\n  组件详情:")
            print(f"  杯沿 (Cup Edge):")
            cup_edge = pred.components['cup_edge']
            print(f"    是否检测: {'是' if cup_edge['detected'] else '否'}")
            if cup_edge['detected']:
                print(f"    质量: {cup_edge.get('quality', 0):.2f}")
                print(f"    震荡天数: {cup_edge.get('days_consolidating', 0)} 天")
                print(f"    价格距离: {abs(cup_edge.get('current_price', 0) - cup_edge.get('handle_level', 0)) / cup_edge.get('handle_level', 0) * 100:.1f}%")

            print(f"\n  成交量:")
            sent = pred.components['sentiment']
            print(f"    量能趋势: {sent.get('vol_trend', 0):.2f} ({'放' if sent.get('vol_trend', 0) > 0 else '平'})")
            print(f"    相对量能: {sent.get('vol_vs_avg', 0):.2f}")
            print(f"    换手率: {sent.get('avg_turnover', 0):.2f}%")
            print(f"    异常放量: {sent.get('volume_spikes', 0)} 次")
            print(f"    情绪评分: {sent.get('sentiment_score', 0):.2f}/100")

            print(f"\n  资金结构:")
            capital = pred.components['capital']
            print(f"    结构: {capital.get('structure', 'unknown')}")
            print(f"    换手率主导: {'是' if capital.get('retail_dominance', 0) else '否'}")
            print(f"    波动率: {capital.get('volatility', 0):.2f}")
            print(f"    量稳定性: {capital.get('vol_consistency', 0):.2f}")

            print(f"\n  涨停板临近度:")
            limit_up = sent.get('limit_up_proximity', 0)
            print(f"    临近度: {limit_up:.2f}")
            print(f"    档次: {sent.get('limit_up_level', 'none')}")

            print(f"\n  预测因子:")
            factors = pred.factors
            for factor_name, value in factors.items():
                print(f"    {factor_name}: {value:.2f}x")

            print(f"  基础概率: {pred.base_probability:.1f}%")
            print(f"  调整后概率: {pred.adjusted_probability:.1f}%")

            print(f"{'─' * 60}")

        except Exception as e:
            print(f"❌ 分析 {code} 时出错: {e}")
            logger.exception(e)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
