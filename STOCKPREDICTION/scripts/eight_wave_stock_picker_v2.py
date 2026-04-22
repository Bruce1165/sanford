"""
eight_wave_stock_picker_v2.py - 基于八段论方法论的选股脚本（使用行业分类）

八段论：五浪上升（1-2-3-4-5）+ 三浪下降（A-B-C）
"""

import sqlite3
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EightWaveStockPickerV2:
    def __init__(self, db_path: str, lookback_days: int = 60):
        self.db_path = db_path
        self.lookback_days = lookback_days

    def get_target_stocks(self) -> list:
        """获取指定领域的股票代码 - 使用行业分类"""
        # 目标行业分类（根据数据库中的实际行业名称）
        target_industries = [
            # 人工智能相关
            '软件服务', '互联网', '通信设备', '电气设备', 'IT设备',

            # 东数西算相关
            '半导体', '电气设备', '元器件',

            # 创新药相关
            '化学制药', '生物制药', '医疗保健',

            # 储能相关
            '电气设备', '汽车配件',

            # 绿色电力相关
            '电气设备', '环境保护',

            # 国产算力相关
            '半导体', '软件服务', '通信设备'
        ]

        # 构建行业过滤SQL
        industry_filters = []
        for industry in target_industries:
            industry_filters.append(f"industry = '{industry}'")

        industry_filter_sql = ' OR '.join(industry_filters)

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            stocks = conn.execute(f"""
                SELECT code, name, industry, circulating_market_cap, pe_ratio, roe
                FROM stocks
                WHERE COALESCE(is_delisted, 0) = 0
                  AND name NOT LIKE '%ST%' AND name NOT LIKE '%*ST%'
                  AND name NOT LIKE '%退%' AND name NOT LIKE '%指数%'
                  AND name NOT LIKE '%ETF%' AND name NOT LIKE '%LOF%'
                  AND code NOT LIKE '43%' AND code NOT LIKE '83%'
                  AND code NOT LIKE '87%' AND code NOT LIKE '88%'
                  AND code NOT LIKE '399%'
                  AND ({industry_filter_sql})
                ORDER BY circulating_market_cap DESC
            """).fetchall()

        return stocks

    def get_stock_data(self, code: str, days: int = None) -> pd.DataFrame:
        """获取单只股票的价格数据"""
        if days is None:
            days = self.lookback_days + 34  # 34天预测期

        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 60)).strftime('%Y-%m-%d')

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            df = pd.read_sql_query("""
                SELECT trade_date, open, high, low, close, volume, amount, turnover, pct_change
                FROM daily_prices
                WHERE code = ? AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date DESC
                LIMIT ?
            """, conn, params=(code, start_date, end_date, days))

        if not df.empty:
            df['trade_date'] = pd.to_datetime(df['trade_date'])

        return df

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        if len(df) < self.lookback_days:
            return None

        df = df.sort_values('trade_date').reset_index(drop=True)

        # 移动平均线
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()

        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=14).mean()

        # 布林带
        df['bollinger_middle'] = df['close'].rolling(window=20).mean()
        std = df['close'].rolling(window=20).std()
        df['bollinger_upper'] = df['bollinger_middle'] + (std * 2)
        df['bollinger_lower'] = df['bollinger_middle'] - (std * 2)
        df['bollinger_pct'] = (df['close'] - df['bollinger_lower']) / (df['bollinger_upper'] - df['bollinger_lower'])

        # 动量指标
        df['return_5d'] = df['close'].pct_change(5)
        df['return_10d'] = df['close'].pct_change(10)
        df['return_20d'] = df['close'].pct_change(20)

        # 成交量指标
        df['vol_ma5'] = df['volume'].rolling(window=5).mean()
        df['vol_ma20'] = df['volume'].rolling(window=20).mean()
        df['vol_ratio_5'] = df['volume'] / df['vol_ma5']
        df['vol_ratio_20'] = df['volume'] / df['vol_ma20']

        return df

    def analyze_stock_wave_phase(self, df: pd.DataFrame) -> dict:
        """分析个股所处的八段论阶段"""
        if df is None or len(df) < 20:
            return None

        latest = df.iloc[-1]
        recent_20 = df.tail(20)
        recent_30 = df.tail(30)

        # 计算近期涨跌
        recent_20_return = (latest['close'] / recent_20.iloc[0]['close'] - 1) * 100
        recent_30_return = (latest['close'] / recent_30.iloc[0]['close'] - 1) * 100

        # 均线排列
        ma_bullish = latest['ma5'] > latest['ma10'] > latest['ma20'] > latest['ma60']
        ma_bearish = latest['ma5'] < latest['ma10'] < latest['ma20'] < latest['ma60']

        # MACD信号
        macd_golden = latest['macd'] > latest['macd_signal'] and latest['macd_hist'] > 0
        macd_death = latest['macd'] < latest['macd_signal'] and latest['macd_hist'] < 0

        # RSI状态
        rsi_overbought = latest['rsi'] > 70
        rsi_oversold = latest['rsi'] < 30

        # 成交量放大
        vol_expansion = latest['vol_ratio_5'] > 1.5

        # 判断八段论阶段
        phase_score = 0
        phase_reason = []

        # 上升浪特征
        if ma_bullish:
            phase_score += 20
            phase_reason.append("均线多头排列")
        if macd_golden:
            phase_score += 15
            phase_reason.append("MACD金叉")
        if not rsi_overbought and latest['rsi'] > 50:
            phase_score += 10
            phase_reason.append("RSI上升但不超买")
        if vol_expansion:
            phase_score += 10
            phase_reason.append("成交量放大")

        # 主升浪特征（第3浪）
        if ma_bullish and macd_golden and vol_expansion and recent_20_return > 10:
            phase_score += 25
            phase_reason.append("主升浪特征")

        # 上涨回调特征（第2浪、第4浪）
        if ma_bullish and 40 < latest['rsi'] < 70:
            phase_score -= 10
            phase_reason.append("上涨回调")

        # 下降浪特征（浪A、浪C）
        if ma_bearish:
            phase_score -= 30
            phase_reason.append("均线空头排列")
        if macd_death:
            phase_score -= 20
            phase_reason.append("MACD死叉")
        if rsi_oversold:
            phase_score -= 10
            phase_reason.append("RSI超卖")

        # 调整浪特征（浪B）
        if not ma_bullish and not ma_bearish:
            phase_score -= 5
            phase_reason.append("均线纠缠")

        return {
            'phase_score': phase_score,
            'phase_reason': phase_reason,
            'recent_20_return': recent_20_return,
            'recent_30_return': recent_30_return
        }

    def calculate_potential_score(self, df: pd.DataFrame, wave_analysis: dict, stock_info: tuple) -> dict:
        """计算股票潜力评分"""
        if df is None or wave_analysis is None:
            return None

        latest = df.iloc[-1]

        # 基础分（八段论阶段）
        base_score = max(0, wave_analysis['phase_score'])

        # 技术面加分
        tech_score = 0
        tech_reasons = []

        # 均线多头排列
        if latest['ma5'] > latest['ma10'] > latest['ma20']:
            tech_score += 20
            tech_reasons.append("均线多头排列")

        # MACD金叉向上
        if latest['macd_hist'] > 0:
            tech_score += 15
            tech_reasons.append("MACD金叉向上")

        # RSI合理（50-70之间为佳）
        if 50 <= latest['rsi'] <= 70:
            tech_score += 10
            tech_reasons.append("RSI合理区间")
        elif 30 < latest['rsi'] < 50:
            tech_score += 5
            tech_reasons.append("RSI偏低，有上涨空间")

        # 成交量放大
        if latest['vol_ratio_5'] > 1.3:
            tech_score += 15
            tech_reasons.append("成交量放大")
        elif latest['vol_ratio_5'] > 1.1:
            tech_score += 8
            tech_reasons.append("成交量温和放大")

        # 价格相对位置（布林带）
        if 0.2 < latest['bollinger_pct'] < 0.8:
            tech_score += 10
            tech_reasons.append("价格在中位")

        # 基本面加分
        code, name, industry, market_cap, pe_ratio, roe = stock_info
        fundamental_score = 0
        fund_reasons = []

        # ROE指标
        if not pd.isna(roe) and roe > 10:
            fundamental_score += 15
            fund_reasons.append(f"ROE高({roe:.2f}%)")
        elif not pd.isna(roe) and roe > 5:
            fundamental_score += 8
            fund_reasons.append(f"ROE良好({roe:.2f}%)")

        # PE指标（合理PE为10-30）
        if not pd.isna(pe_ratio) and 10 <= pe_ratio <= 30:
            fundamental_score += 10
            fund_reasons.append(f"PE合理({pe_ratio:.2f})")

        # 综合评分
        total_score = base_score + tech_score + fundamental_score

        return {
            'code': code,
            'name': name,
            'industry': industry,
            'market_cap': market_cap,
            'close': latest['close'],
            'base_score': base_score,
            'tech_score': tech_score,
            'fundamental_score': fundamental_score,
            'total_score': total_score,
            'phase_reason': wave_analysis['phase_reason'],
            'tech_reasons': tech_reasons,
            'fund_reasons': fund_reasons,
            'recent_20_return': wave_analysis['recent_20_return'],
            'recent_30_return': wave_analysis['recent_30_return'],
        }

    def pick_stocks(self, top_n: int = 50) -> list:
        """选股"""
        logger.info("开始基于八段论方法论选股（使用行业分类）...")

        # 获取目标领域股票
        stocks = self.get_target_stocks()
        logger.info(f"目标领域股票数量: {len(stocks)}")

        results = []
        processed = 0

        for code, name, industry, market_cap, pe_ratio, roe in stocks:
            try:
                # 获取价格数据
                df = self.get_stock_data(code)
                if df is None or len(df) < self.lookback_days:
                    processed += 1
                    if processed % 100 == 0:
                        logger.info(f"已处理 {processed}/{len(stocks)} 只股票")
                    continue

                # 计算技术指标
                df = self.calculate_technical_indicators(df)
                if df is None:
                    continue

                # 分析八段论阶段
                wave_analysis = self.analyze_stock_wave_phase(df)
                if wave_analysis is None:
                    continue

                # 计算潜力评分
                stock_score = self.calculate_potential_score(df, wave_analysis,
                                                                    (code, name, industry, market_cap, pe_ratio, roe))
                if stock_score is None:
                    continue

                results.append(stock_score)
                processed += 1

                if processed % 100 == 0:
                    logger.info(f"已处理 {processed}/{len(stocks)} 只股票")

            except Exception as e:
                logger.warning(f"处理股票 {code} 时出错: {e}")
                continue

        # 转换为DataFrame并排序
        if results:
            df_results = pd.DataFrame(results)
            df_results = df_results.sort_values('total_score', ascending=False)
            top_stocks = df_results.head(top_n).to_dict('records')
        else:
            top_stocks = []

        logger.info(f"选股完成，共推荐 {len(top_stocks)} 只股票")

        return top_stocks

    def save_results(self, results: list, output_path: str = None):
        """保存选股结果"""
        if output_path is None:
            output_path = Path(f"data/picks/eight_wave_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        df_results = pd.DataFrame(results)
        df_results.to_excel(output_path, index=False)
        logger.info(f"选股结果已保存到: {output_path}")

        return str(output_path)


def main():
    db_path = "/Users/mac/NeoTrade2/data/stock_data.db"

    picker = EightWaveStockPickerV2(db_path)

    # 选股
    top_stocks = picker.pick_stocks(top_n=50)

    if top_stocks:
        # 显示结果
        print("=" * 100)
        print(f"基于八段论方法论的选股结果（推荐未来21-34天内上涨20%的潜力股）")
        print("=" * 100)
        print(f"分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"推荐数量：{len(top_stocks)} 只股票")
        print()

        # 显示前10名
        print("【前10名推荐股票】")
        print(f"{'排名':<5} {'代码':<8} {'名称':<20} {'行业':<20} {'综合评分':<8} {'阶段评分':<8} {'技术评分':<8} {'基本面评分':<8} {'近期20日涨幅':<10}")
        print("-" * 100)

        for i, stock in enumerate(top_stocks[:10], 1):
            print(f"{i:<5d} {stock['code']:<8s} {stock['name']:<20s} {stock['industry']:<20s} {stock['total_score']:<8.1f} {stock['base_score']:<8.1f} {stock['tech_score']:<8.1f} {stock['fundamental_score']:<8.1f} {stock['recent_20_return']:>8.2f}%")
            print(f"     阶段特征: {', '.join(stock['phase_reason'][:3])}")
            print(f"     技术特征: {', '.join(stock['tech_reasons'][:2])}")
            print(f"     基本面特征: {', '.join(stock['fund_reasons'][:2])}")
            print()

        print("-" * 100)
        print("【行业分布统计】")
        industry_count = {}
        for stock in top_stocks:
            industry = stock['industry']
            industry_count[industry] = industry_count.get(industry, 0) + 1

        for industry, count in sorted(industry_count.items(), key=lambda x: x[1], reverse=True):
            print(f"  {industry}: {count} 只")

        print("-" * 100)
        print("【说明】")
        print("1. 基于八段论：五浪上升（1-2-3-4-5）+ 三浪下降（A-B-C）")
        print("2. 使用行业分类：人工智能（软件服务/互联网/通信设备）、东数西算（半导体/电气设备）、创新药（化学制药/生物制药）、储能（电气设备/汽车配件）、绿色电力（电气设备/环境保护）、国产算力（半导体/软件服务/通信设备）")
        print("3. 阶段评分：基于均线排列、MACD、RSI、成交量等指标判断个股所处阶段")
        print("4. 技术评分：均线多头、MACD金叉、RSI合理、成交量放大等")
        print("5. 基本面评分：ROE、PE等指标")
        print("6. 综合评分 = 阶段评分 + 技术评分 + 基本面评分")
        print("7. 仅基于DB现有数据（价格、基本面），未包含宏观经济、政策、资金流向等外部数据")
        print("=" * 100)

        # 保存结果
        output_path = picker.save_results(top_stocks)
        print(f"\n完整结果已保存到: {output_path}")
    else:
        print("未找到符合条件的股票")


if __name__ == '__main__':
    main()
