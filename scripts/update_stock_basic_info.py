#!/usr/bin/env python3
"""
补充股票基础数据 - 市值、行业、市净率
使用 AKShare 获取并更新到数据库
"""

import os
import sys
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from database import init_db, get_session, Stock

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = WORKSPACE_ROOT / "data" / "stock_data.db"


def update_stock_basic_info():
    """使用 AKShare 更新股票基础信息（市值、行业、市净率）"""
    try:
        import akshare as ak
        
        logger.info("="*60)
        logger.info("开始更新股票基础信息（市值、行业、市净率）")
        logger.info("="*60)
        
        # 获取所有A股实时行情（包含市值、行业等信息）
        logger.info("从 AKShare 获取股票基础数据...")
        df = ak.stock_zh_a_spot_em()
        logger.info(f"获取到 {len(df)} 只股票数据")
        
        # 连接数据库
        engine = init_db()
        session = get_session(engine)
        
        updated = 0
        skipped = 0
        
        for _, row in df.iterrows():
            code = str(row.get('代码', '')).strip()
            if not code:
                continue
            
            # 查找股票记录
            stock = session.query(Stock).filter_by(code=code).first()
            if not stock:
                skipped += 1
                continue
            
            # 更新字段
            try:
                # 行业
                industry = row.get('所属行业', '')
                if industry and industry != '-':
                    stock.industry = industry
                
                # AB股总市值（元）
                total_cap = row.get('总市值')
                if pd.notna(total_cap):
                    stock.total_market_cap = float(total_cap)
                
                # 流通市值（元）
                circ_cap = row.get('流通市值')
                if pd.notna(circ_cap):
                    stock.circulating_market_cap = float(circ_cap)
                
                # 市净率
                pb = row.get('市净率')
                if pd.notna(pb):
                    stock.pb_ratio = float(pb)
                
                stock.updated_at = datetime.now()
                updated += 1
                
                if updated % 500 == 0:
                    logger.info(f"已更新 {updated} 只股票...")
                    session.commit()
                    
            except Exception as e:
                logger.warning(f"更新 {code} 失败: {e}")
                continue
        
        session.commit()
        session.close()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"更新完成!")
        logger.info(f"更新: {updated} 只股票")
        logger.info(f"跳过: {skipped} 只股票（数据库中不存在）")
        logger.info(f"{'='*60}")
        
        return updated
        
    except ImportError:
        logger.error("请先安装 AKShare: pip install akshare")
        return 0
    except Exception as e:
        logger.error(f"更新失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def main():
    """主函数"""
    import pandas as pd  # AKShare 依赖 pandas
    
    updated = update_stock_basic_info()
    
    if updated > 0:
        print(f"\n✓ 成功更新 {updated} 只股票的基础信息")
    else:
        print("\n✗ 更新失败或未更新任何股票")


if __name__ == '__main__':
    main()
