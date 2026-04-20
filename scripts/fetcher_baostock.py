#!/usr/bin/env python3
"""
Baostock数据抓取器 - 全A股日线数据
"""
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaostockFetcher:
    """Baostock数据抓取器"""
    
    def __init__(self):
        self.lg = None
        
    def login(self):
        """登录Baostock"""
        self.lg = bs.login()
        if self.lg.error_code != '0':
            logger.error(f"登录失败: {self.lg.error_msg}")
            return False
        logger.info(f"登录成功")
        return True
    
    def logout(self):
        """登出"""
        if self.lg:
            bs.logout()
            logger.info("已登出")
    
    def get_stock_list(self):
        """获取全A股列表"""
        logger.info("获取全A股列表...")
        
        # 获取所有股票
        rs = bs.query_stock_basic(code_name="", code="")
        
        stocks = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            code = row[0]  # sh.600000 或 sz.000001 格式
            name = row[1] if len(row) > 1 else ""
            
            # 过滤ST股
            if 'ST' in name.upper():
                continue
            
            # 过滤北交所 (bj.开头)
            if code.startswith('bj.'):
                continue
            
            # 只保留A股个股（sh.或sz.开头，且是6位数字代码）
            if code.startswith('sh.') or code.startswith('sz.'):
                stock_code = code.split('.')[1]
                # 个股代码：600/601/603/605/688(科创) 或 000/001/002/003/300/301(创业)
                if len(stock_code) == 6 and stock_code[0] in ['0', '3', '6']:
                    stocks.append({
                        'code': code,
                        'name': name
                    })
        
        logger.info(f"获取到 {len(stocks)} 只股票（已过滤ST、北交所、指数）")
        return stocks
    
    def get_stock_info(self, code):
        """获取单只股票基础信息"""
        rs = bs.query_stock_basic(code=code)
        
        if rs.error_code != '0':
            logger.warning(f"获取{code}基础信息失败: {rs.error_msg}")
            return None
        
        if rs.next():
            row = rs.get_row_data()
            # fields: code, code_name, ipoDate, outDate, type, status
            out_date = row[3] if len(row) > 3 else ''
            return {
                'code': row[0].replace('sh.', '').replace('sz.', ''),
                'name': row[1] if len(row) > 1 else '',
                'list_date': row[2] if len(row) > 2 else None,
                'out_date': out_date,
                'asset_type': 'stock',
                'is_delisted': 1 if out_date else 0,
            }
        return None
    
    def get_daily_data(self, code, start_date, end_date):
        """获取日线数据"""
        fields = "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg"
        
        rs = bs.query_history_k_data_plus(
            code,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 前复权
        )
        
        if rs.error_code != '0':
            logger.warning(f"获取{code}日线数据失败: {rs.error_msg}")
            return pd.DataFrame()
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            data_list.append(row)
        
        if not data_list:
            return pd.DataFrame()
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 数据类型转换
        numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'turn', 'pctChg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def fetch_all_daily_data(self, start_date, end_date, batch_size=100):
        """批量获取全A股日线数据"""
        if not self.login():
            return pd.DataFrame()
        
        try:
            stocks = self.get_stock_list()
            all_data = []
            
            total = len(stocks)
            for i, stock in enumerate(stocks):
                code = stock['code']
                logger.info(f"[{i+1}/{total}] 获取 {code} 数据...")
                
                df = self.get_daily_data(code, start_date, end_date)
                if not df.empty:
                    all_data.append(df)
                
                # 每100只暂停一下，避免请求过快
                if (i + 1) % batch_size == 0:
                    logger.info(f"已处理 {i+1}/{total} 只，暂停2秒...")
                    import time
                    time.sleep(2)
            
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                logger.info(f"共获取 {len(result)} 条日线数据")
                return result
            else:
                return pd.DataFrame()
        
        finally:
            self.logout()

if __name__ == '__main__':
    fetcher = BaostockFetcher()
    
    # 测试：获取最近6个月数据
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    
    df = fetcher.fetch_all_daily_data(start_date, end_date)
    print(f"\n获取到 {len(df)} 条数据")
    if not df.empty:
        print(df.head())
