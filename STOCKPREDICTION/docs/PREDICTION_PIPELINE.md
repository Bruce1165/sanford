# 预测流程

## 概述

本文档描述每日股票预测的完整流程，从数据获取到结果输出。

## 流程概览

```
┌─────────────────────────────────────────────────────────────────┐
│                  1. 数据获取阶段                                │
│  - 获取 NeoTrade2 最新数据                                     │
│  - 确定最新交易日                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  2. 特征计算阶段                                │
│  - 计算当日技术指标                                            │
│  - 运行当日筛选器                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  3. 预测执行阶段                                │
│  - 加载模型                                                    │
│  - 准备特征矩阵                                                │
│  - 执行预测                                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  4. 结果处理阶段                                │
│  - 排序和筛选                                                  │
│  - 保存预测结果                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  5. 结果输出阶段                                │
│  - 生成报告                                                    │
│  - 更新 Dashboard                                              │
│  - 发送通知（可选）                                            │
└─────────────────────────────────────────────────────────────────┘
```

## 1. 数据获取阶段

### 1.1 确定最新交易日

```python
import sqlite3
from pathlib import Path
from datetime import datetime

NEOTRADE_DB = Path("/Users/mac/NeoTrade2/data/stock_data.db")

def get_latest_trading_date():
    """获取最新的交易日"""
    with sqlite3.connect(str(NEOTRADE_DB), timeout=30) as conn:
        row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
        return row[0] if row and row[0] else datetime.now().strftime("%Y-%m-%d")

# 使用
latest_date = get_latest_trading_date()
print(f"最新交易日: {latest_date}")
```

### 1.2 验证数据完整性

```python
def verify_data_integrity(date_str):
    """验证指定日期的数据完整性"""
    with sqlite3.connect(str(NEOTRADE_DB), timeout=30) as conn:
        # 检查数据量
        count = conn.execute("""
            SELECT COUNT(*) FROM daily_prices WHERE trade_date = ?
        """, (date_str,)).fetchone()[0]

        # 检查数据质量
        null_count = conn.execute("""
            SELECT COUNT(*) FROM daily_prices
            WHERE trade_date = ? AND (close IS NULL OR volume IS NULL)
        """, (date_str,)).fetchone()[0]

    if count < 4000:  # 预期约 4600 只股票
        return False, f"数据量不足: {count} 条"

    if null_count > 0:
        return False, f"存在 {null_count} 条空数据"

    return True, "数据完整"

# 使用
is_valid, message = verify_data_integrity(latest_date)
if not is_valid:
    print(f"数据验证失败: {message}")
    exit(1)
```

## 2. 特征计算阶段

### 2.1 计算技术特征

```python
from scripts.compute_features import FeatureEngine

engine = FeatureEngine()

# 获取所有股票
stocks = engine.get_all_stocks()

# 为当天计算特征
for code, name in stocks:
    try:
        count = engine.compute_for_stock(code, name, latest_date, latest_date)
    except Exception as e:
        print(f"计算 {code} 特征失败: {e}")
```

### 2.2 运行筛选器

```python
from scripts.collect_screener_scores import ScreenerFeatureCollector

collector = ScreenerFeatureCollector()

# 运行所有筛选器
for screener_name in collector.available_screeners:
    results = collector.run_screener(screener_name, latest_date)
    collector.save_screener_results(screener_name, latest_date, results)
    hit_count = sum(1 for r in results.values() if r['hit'])
    print(f"  {screener_name}: 命中 {hit_count} 只股票")
```

## 3. 预测执行阶段

### 3.1 加载模型和元数据

```python
import xgboost as xgb
import json
from pathlib import Path

# 加载模型
model_path = Path('models/xgboost_model.json')
model = xgb.XGBClassifier()
model.load_model(str(model_path))

# 加载元数据
metadata_path = Path('models/model_metadata.json')
with open(metadata_path, 'r') as f:
    metadata = json.load(f)

feature_names = metadata['features']
```

### 3.2 准备预测数据

```python
import pandas as pd
import sqlite3

# 加载当日特征
with sqlite3.connect('data/features.db') as conn:
    features_df = pd.read_sql_query("""
        SELECT * FROM stock_features WHERE trade_date = ?
    """, conn, params=(latest_date,))

# 加载筛选器特征
with sqlite3.connect('data/screener_scores.db') as conn:
    screener_df = pd.read_sql_query("""
        SELECT * FROM screener_features WHERE trade_date = ?
    """, conn, params=(latest_date,))

# 编码筛选器特征
screener_pivot = screener_df.pivot_table(
    index='code',
    columns='screener_name',
    values='hit',
    fill_value=0
).reset_index()

# 合并数据
predict_data = features_df.merge(screener_pivot, on='code', how='left')

# 准备特征矩阵
X = predict_data[feature_names].copy()

# 填充缺失值
X = X.fillna(0)

# 获取股票列表
codes = predict_data['code'].tolist()
names = predict_data.get('name', [''] * len(codes)).tolist()
```

### 3.3 执行预测

```python
# 预测概率
probabilities = model.predict_proba(X)[:, 1]

# 创建结果 DataFrame
predictions = pd.DataFrame({
    'code': codes,
    'name': names,
    'probability': probabilities,
    'prediction_date': latest_date
})

# 添加排名
predictions['rank'] = predictions['probability'].rank(ascending=False)

print(f"完成 {len(predictions)} 只股票的预测")
```

## 4. 结果处理阶段

### 4.1 筛选高概率股票

```python
# 按概率排序
predictions_sorted = predictions.sort_values('probability', ascending=False)

# 获取 Top K
TOP_K = 50
top_predictions = predictions_sorted.head(TOP_K)

print(f"\nTop {TOP_K} 预测:")
print(top_predictions[['rank', 'code', 'name', 'probability']].to_string(index=False))
```

### 4.2 保存预测结果

```python
def save_predictions(predictions, db_path='data/predictions.db'):
    """保存预测结果到数据库"""
    with sqlite3.connect(db_path) as conn:
        for _, row in predictions.iterrows():
            conn.execute("""
                INSERT INTO predictions
                (code, name, prediction_date, probability, rank,
                 model_name, model_version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                row['code'],
                row['name'],
                row['prediction_date'],
                row['probability'],
                int(row['rank']),
                'xgboost',
                '1.0.0'
            ))
        conn.commit()

    print(f"预测结果已保存: {db_path}")

# 保存
save_predictions(predictions)
```

## 5. 结果输出阶段

### 5.1 生成报告

```python
from datetime import datetime

def generate_report(predictions, date_str, output_path='reports/daily_prediction.txt'):
    """生成每日预测报告"""
    report_lines = [
        f"=== 股票预测报告 ===",
        f"日期: {date_str}",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"预测股票数: {len(predictions)}",
        "",
        f"=== Top 20 预测 ===",
    ]

    top_20 = predictions.head(20)
    for _, row in top_20.iterrows():
        report_lines.append(
            f"{row['rank']:3d}. {row['code']:8s} {row['name']:12s} "
            f"概率: {row['probability']:.4f}"
        )

    report = '\n'.join(report_lines)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n{report}")
    print(f"\n报告已保存: {output_path}")

# 生成报告
generate_report(predictions, latest_date)
```

### 5.2 导出 Excel

```python
def export_to_excel(predictions, date_str, output_path='reports/daily_prediction.xlsx'):
    """导出到 Excel"""
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        # Top 100
        predictions.head(100).to_excel(
            writer, sheet_name='Top100', index=False
        )

        # 概率分布
        prob_dist = pd.cut(predictions['probability'], bins=10).value_counts().sort_index()
        prob_dist.to_excel(writer, sheet_name='概率分布')

        # 统计信息
        stats = pd.DataFrame({
            '指标': ['总预测数', '平均概率', '最大概率', '最小概率'],
            '值': [
                len(predictions),
                predictions['probability'].mean(),
                predictions['probability'].max(),
                predictions['probability'].min()
            ]
        })
        stats.to_excel(writer, sheet_name='统计', index=False)

    print(f"Excel 报告已保存: {output_path}")

# 导出
export_to_excel(predictions, latest_date)
```

### 5.3 发送通知（可选）

```python
import subprocess

def send_notification(message):
    """发送 macOS 通知"""
    subprocess.run([
        'osascript', '-e',
        f'display notification "{message}" with title "股票预测"'
    ])

# 发送通知
send_notification(f"预测完成！Top 10 平均概率: {top_10['probability'].mean():.2%}")
```

## 完整预测脚本

```python
#!/usr/bin/env python3
"""
predict.py - 每日股票预测脚本
"""

import argparse
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/prediction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyPredictor:
    """每日预测器"""

    def __init__(self, model_path=None, date_str=None):
        self.model_path = Path(model_path) if model_path else Path('models/xgboost_model.json')
        self.date_str = date_str
        self.model = None
        self.metadata = None

    def load_model(self):
        """加载模型和元数据"""
        import xgboost as xgb
        import json

        logger.info(f"加载模型: {self.model_path}")
        self.model = xgb.XGBClassifier()
        self.model.load_model(str(self.model_path))

        metadata_path = self.model_path.parent / 'model_metadata.json'
        with open(metadata_path, 'r') as f:
            self.metadata = json.load(f)

        self.feature_names = self.metadata['features']
        logger.info(f"模型加载完成，特征数: {len(self.feature_names)}")

    def prepare_data(self):
        """准备预测数据"""
        import pandas as pd
        import sqlite3
        from scripts.config import NEOTRADE_DB_PATH

        # 确定日期
        if not self.date_str:
            with sqlite3.connect(str(NEOTRADE_DB_PATH)) as conn:
                row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
                self.date_str = row[0] if row and row[0] else None

        logger.info(f"预测日期: {self.date_str}")

        # 加载特征
        with sqlite3.connect('data/features.db') as conn:
            self.features_df = pd.read_sql_query(
                "SELECT * FROM stock_features WHERE trade_date = ?",
                conn, params=(self.date_str,)
            )

        # 加载筛选器特征
        with sqlite3.connect('data/screener_scores.db') as conn:
            screener_df = pd.read_sql_query(
                "SELECT * FROM screener_features WHERE trade_date = ?",
                conn, params=(self.date_str,)
            )

        # 编码筛选器
        screener_pivot = screener_df.pivot_table(
            index='code', columns='screener_name', values='hit', fill_value=0
        ).reset_index()

        # 合并
        self.predict_data = self.features_df.merge(screener_pivot, on='code', how='left')
        self.X = self.predict_data[self.feature_names].fillna(0)

        logger.info(f"准备数据完成: {len(self.X)} 只股票")

    def predict(self):
        """执行预测"""
        self.probabilities = self.model.predict_proba(self.X)[:, 1]

        self.predictions = pd.DataFrame({
            'code': self.predict_data['code'],
            'name': self.predict_data.get('name', ''),
            'probability': self.probabilities,
            'prediction_date': self.date_str
        })

        self.predictions['rank'] = self.predictions['probability'].rank(ascending=False)
        self.predictions = self.predictions.sort_values('rank')

        logger.info(f"预测完成")

    def save_results(self):
        """保存结果"""
        import sqlite3

        with sqlite3.connect('data/predictions.db') as conn:
            for _, row in self.predictions.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO predictions
                    (code, name, prediction_date, probability, rank,
                     model_name, model_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['code'], row['name'], row['prediction_date'],
                    row['probability'], int(row['rank']),
                    'xgboost', '1.0.0'
                ))
            conn.commit()

        logger.info(f"结果已保存到数据库")

    def generate_report(self):
        """生成报告"""
        top_50 = self.predictions.head(50)

        report = f"""
=== 股票预测报告 ===
日期: {self.date_str}
总预测数: {len(self.predictions)}

=== Top 50 预测 ===
{'排名':<5} {'代码':<10} {'名称':<15} {'概率':<10}
{'-'*40}
"""
        for _, row in top_50.iterrows():
            report += f"{int(row['rank']):<5} {row['code']:<10} {row['name']:<15} {row['probability']:.4f}\n"

        logger.info(f"\n{report}")

        # 保存报告
        report_path = Path('reports') / f"prediction_{self.date_str}.txt"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"报告已保存: {report_path}")

    def run(self):
        """运行完整预测流程"""
        self.load_model()
        self.prepare_data()
        self.predict()
        self.save_results()
        self.generate_report()


def main():
    parser = argparse.ArgumentParser(description='每日股票预测')
    parser.add_argument('--model', type=str, help='模型文件路径')
    parser.add_argument('--date', type=str, help='预测日期 (YYYY-MM-DD)')
    parser.add_argument('--top-k', type=int, default=50, help='输出 Top K')

    args = parser.parse_args()

    predictor = DailyPredictor(model_path=args.model, date_str=args.date)
    predictor.run()


if __name__ == '__main__':
    main()
```

## 自动化运行

### Cron 任务

```bash
# 编辑 crontab
crontab -e

# 添加任务
30 15 * * 1-5 cd /Users/mac/NeoTrade2/STOCKPREDICTION && \
    source venv/bin/activate && \
    python scripts/predict.py >> logs/cron_prediction.log 2>&1
```

### Launchd (macOS)

创建 `~/Library/LaunchAgents/com.stockprediction.predictor.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stockprediction.predictor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/mac/NeoTrade2/STOCKPREDICTION/venv/bin/python</string>
        <string>/Users/mac/NeoTrade2/STOCKPREDICTION/scripts/predict.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/mac/NeoTrade2/STOCKPREDICTION</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>15</integer>
        <key>Minute</key>
        <integer>30</integer>
        <key>Weekday</key>
        <integer>1</integer>
        <integer>2</integer>
        <integer>3</integer>
        <integer>4</integer>
        <integer>5</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/mac/NeoTrade2/STOCKPREDICTION/logs/predictor.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mac/NeoTrade2/STOCKPREDICTION/logs/predictor_error.log</string>
</dict>
</plist>
```

加载任务:
```bash
launchctl load ~/Library/LaunchAgents/com.stockprediction.predictor.plist
```
