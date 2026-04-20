#!/usr/bin/env python3
"""
覆盖所有历史数据的 amount 字段

使用 backfill_baostock 脚本的逻辑
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from config import DB_PATH

# 设置参数
MIN_DATA_DAYS = 120  # 最少需要的历史数据天数

def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='覆盖 amount 字段')
    parser.add_argument('--start-date', type=str, help='开始日期 (YYYY-MM-DD)')
    args = parser.parse_args()

    # 计算结束日期
    end_date = datetime.now().strftime('%Y-%m-%d')

    # 开始日期
    if args.start_date:
        start_date = args.start_date
    else:
        # 默认获取所有数据，从最早有数据的日期开始
        start_date = (datetime.now() - timedelta(days=MIN_DATA_DAYS)).strftime('%Y-%m-%d')

    print(f"数据范围: {start_date} 到 {end_date}")
    print(f"目标股票: 全部")

    # 导入 backfill 模块
    sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
    from backfill_baostock import run_backfill

    # 调用 backfill
    try:
        result = run_backfill(
            start_date=start_date,
            end_date=end_date,
            full=True,
            dry_run=False
        )

        if result.get('errors', 0) > 0:
            print(f"\\n处理完成!")
            print(f"成功: {result.get('success', 0)}")
            print(f"总处理: {result.get('total', 0)}")
            print(f"插入: {result.get('inserted', 0)}")
            print(f"错误: {result.get('errors', 0)}")
        else:
            print(f"错误信息: {result}")
    except Exception as e:
        print(f"运行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
