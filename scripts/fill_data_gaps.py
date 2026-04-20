#!/usr/bin/env python3
"""
iFind 数据补充脚本 - 补充本地数据库缺失的历史数据
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, '/Users/mac/pilot-ifind')
sys.path.insert(0, os.path.join(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent)), 'scripts'))

from src.client import IfindClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent))) / 'data/stock_data.db'
BATCH_SIZE = 100  # 每批处理100只股票


class DataGapFiller:
    """数据缺口填充器"""
    
    def __init__(self):
        self.client = IfindClient()
        self.db_path = str(DB_PATH)
    
    def get_expected_dates(self, days: int = 250) -> List[str]:
        """获取应该有的交易日列表（最近N天）"""
        dates = []
        end = datetime.now()
        start = end - timedelta(days=days*1.5)  # 多取一些，排除周末
        
        current = start
        while current <= end:
            # 排除周末
            if current.weekday() < 5:  # 0-4 是周一到周五
                dates.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        
        return dates[-days:]  # 只取最后N天
    
    def find_gaps(self, code: str, expected_dates: List[str]) -> List[str]:
        """找出某只股票缺失的日期"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT trade_date FROM daily_prices WHERE code = ? AND trade_date >= ?",
            (code, expected_dates[0])
        )
        existing = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        expected = set(expected_dates)
        missing = expected - existing
        return sorted(list(missing))
    
    def get_all_stocks_with_gaps(self, days: int = 250) -> List[Tuple[str, int]]:
        """获取所有股票及其缺失数据天数"""
        logger.info(f"🔍 扫描最近 {days} 天的数据缺口...")
        
        conn = sqlite3.connect(self.db_path)
        
        # 获取所有股票
        cursor = conn.execute("SELECT DISTINCT code FROM daily_prices")
        all_codes = [row[0] for row in cursor.fetchall()]
        
        # 计算开始日期
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # 统计每只股票的数据量
        stocks_with_gaps = []
        for code in all_codes:
            cursor.execute(
                "SELECT COUNT(*) FROM daily_prices WHERE code = ? AND trade_date >= ?",
                (code, start_date)
            )
            count = cursor.fetchone()[0]
            gaps = days - count if count < days else 0
            if gaps > 0:
                stocks_with_gaps.append((code, gaps))
        
        conn.close()
        
        # 按缺口数量排序（先补缺口多的）
        stocks_with_gaps.sort(key=lambda x: x[1], reverse=True)
        
        total_gaps = sum(g for _, g in stocks_with_gaps)
        logger.info(f"📊 发现 {len(stocks_with_gaps)} 只股票有数据缺口，总计 {total_gaps} 条")
        
        return stocks_with_gaps
    
    def fetch_from_ifind(self, code: str, missing_dates: List[str]) -> List[dict]:
        """从 iFind 获取缺失数据"""
        if not missing_dates:
            return []
        
        # 转换为 iFind 格式
        ifind_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
        
        # API 需要 YYYYMMDD 格式（不带横线）
        start = missing_dates[0].replace('-', '')
        end = missing_dates[-1].replace('-', '')
        
        params = {
            'codes': ifind_code,
            'indicators': 'open,high,low,close,volume,amount,changeRatio',
            'startdate': start,
            'enddate': end,
            'functionpara': {'Fill': 'Blank'}
        }
        
        try:
            result = self.client.post('cmd_history_quotation', params)
            tables = result.get('tables', [])
            
            if not tables:
                return []
            
            table = tables[0]
            table_data = table.get('table', {})
            time_list = table.get('time', [])
            
            if not time_list:
                return []
            
            # 转换为数据库格式
            records = []
            for i, date_str in enumerate(time_list):
                if date_str in missing_dates:
                    records.append({
                        'code': code,
                        'trade_date': date_str,
                        'open': table_data.get('open', [])[i] if i < len(table_data.get('open', [])) else None,
                        'high': table_data.get('high', [])[i] if i < len(table_data.get('high', [])) else None,
                        'low': table_data.get('low', [])[i] if i < len(table_data.get('low', [])) else None,
                        'close': table_data.get('close', [])[i] if i < len(table_data.get('close', [])) else None,
                        'volume': table_data.get('volume', [])[i] if i < len(table_data.get('volume', [])) else None,
                        'amount': table_data.get('amount', [])[i] if i < len(table_data.get('amount', [])) else None,
                        'pct_change': table_data.get('changeRatio', [])[i] if i < len(table_data.get('changeRatio', [])) else None,
                    })
            
            return records
            
        except Exception as e:
            logger.warning(f"   获取 {code} 数据失败: {e}")
            return []
    
    def insert_to_db(self, records: List[dict]):
        """插入数据到数据库"""
        if not records:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        
        inserted = 0
        for r in records:
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO daily_prices 
                       (code, trade_date, open, high, low, close, volume, amount, pct_change, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (r['code'], r['trade_date'], r['open'], r['high'], r['low'], 
                     r['close'], r['volume'], r['amount'], r['pct_change'],
                     datetime.now().isoformat())
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"   插入失败 {r['code']} {r['trade_date']}: {e}")
        
        conn.commit()
        conn.close()
        return inserted
    
    def fill_gaps(self, max_stocks: int = None, days: int = 60):
        """填充数据缺口"""
        stocks_with_gaps = self.get_all_stocks_with_gaps(days=days)
        
        if max_stocks:
            stocks_with_gaps = stocks_with_gaps[:max_stocks]
        
        expected_dates = self.get_expected_dates(days)
        
        total_filled = 0
        total_quota_used = 0
        
        logger.info(f"🚀 开始填充 {len(stocks_with_gaps)} 只股票的数据缺口")
        
        for i, (code, gaps) in enumerate(stocks_with_gaps, 1):
            logger.info(f"[{i}/{len(stocks_with_gaps)}] {code} - 缺口 {gaps} 天")
            
            missing_dates = self.find_gaps(code, expected_dates)
            if not missing_dates:
                continue
            
            records = self.fetch_from_ifind(code, missing_dates)
            if records:
                inserted = self.insert_to_db(records)
                total_filled += inserted
                total_quota_used += len(records)
                logger.info(f"   ✅ 补充 {inserted} 条数据")
            else:
                logger.info(f"   ⚠️ 未获取到数据")
            
            # 每50只显示进度
            if i % 50 == 0:
                logger.info(f"📈 进度: {i}/{len(stocks_with_gaps)}, 已补充 {total_filled} 条, 配额使用 {total_quota_used}")
        
        logger.info(f"\n✅ 完成: 补充 {total_filled} 条数据, iFind 配额使用 {total_quota_used}")
        return total_filled


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='补充本地数据库缺失数据')
    parser.add_argument('--days', type=int, default=60, help='检查最近多少天')
    parser.add_argument('--max', type=int, help='最多处理多少只股票')
    args = parser.parse_args()
    
    filler = DataGapFiller()
    filler.fill_gaps(max_stocks=args.max, days=args.days)


if __name__ == '__main__':
    main()
