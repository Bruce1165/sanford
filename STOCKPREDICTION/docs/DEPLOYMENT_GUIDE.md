# 部署指南

## 概述

本文档描述如何部署和运行 STOCKPREDICTION 系统。

## 系统要求

### 最低配置

- **CPU**: 4 核
- **内存**: 8GB
- **磁盘**: 20GB 可用空间
- **Python**: 3.10+

### 推荐配置

- **CPU**: 8 核
- **内存**: 16GB+
- **磁盘**: 50GB SSD
- **Python**: 3.11

## 安装步骤

### 1. 环境准备

```bash
# 创建项目目录
cd /Users/mac/NeoTrade2/STOCKPREDICTION

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 升级 pip
pip install --upgrade pip
```

### 2. 安装依赖

```bash
# 安装项目依赖
pip install -r requirements.txt

# 验证安装
python -c "import pandas, numpy, xgboost, sklearn; print('OK')"
```

### 3. 配置环境变量

创建 `.env` 文件：

```bash
# NeoTrade2 数据库路径
NEOTRADE_DB_PATH=/Users/mac/NeoTrade2/data/stock_data.db

# 项目路径
WORKSPACE_ROOT=/Users/mac/NeoTrade2/STOCKPREDICTION

# 日志级别
LOG_LEVEL=INFO
```

### 4. 初始化数据库

```bash
# 初始化所有数据库
python -c "from models.database import *; \
    init_db(LABELS_DB); \
    init_db(FEATURES_DB); \
    init_db(SCREENER_SCORES_DB); \
    init_db(PREDICTIONS_DB); \
    print('All databases initialized')"
```

## 数据准备

### 1. 生成训练标签

```bash
# 全量生成
python scripts/backtest_labels.py \
    --start-date 2024-09-01 \
    --end-date 2026-03-31 \
    --overwrite

# 查看统计
python scripts/backtest_labels.py --stats
```

### 2. 计算技术特征

```bash
# 全量计算
python scripts/compute_features.py \
    --start-date 2024-09-01 \
    --end-date 2026-03-31 \
    --overwrite

# 单日计算
python scripts/compute_features.py --date 2026-04-14
```

### 3. 收集筛选器特征

```bash
# 全量收集
python scripts/collect_screener_scores.py \
    --start-date 2024-09-01 \
    --end-date 2026-03-31 \
    --overwrite

# 单日收集
python scripts/collect_screener_scores.py --date 2026-04-14

# 查看统计
python scripts/collect_screener_scores.py --stats
```

## 模型训练

### 基础训练

```bash
python scripts/train_model.py \
    --model xgboost \
    --cv 5 \
    --output models/xgboost_v1.0.json
```

### 参数调优

```bash
python scripts/train_model.py \
    --model xgboost \
    --tune \
    --trials 100 \
    --output models/xgboost_tuned.json
```

## 每日预测

### 手动运行

```bash
# 预测最新日期
python scripts/predict.py \
    --model models/xgboost_v1.0.json

# 预测指定日期
python scripts/predict.py \
    --date 2026-04-14 \
    --model models/xgboost_v1.0.json

# 输出 Top 50
python scripts/predict.py \
    --model models/xgboost_v1.0.json \
    --top-k 50
```

### 自动化运行 (Cron)

编辑 crontab:

```bash
crontab -e
```

添加任务：

```cron
# 每个工作日 15:30 (收盘后) 运行预测
30 15 * * 1-5 cd /Users/mac/NeoTrade2/STOCKPREDICTION && /bin/bash run_daily_prediction.sh >> logs/cron.log 2>&1

# 每周日凌晨 2:00 全量重新计算
0 2 * * 0 cd /Users/mac/NeoTrade2/STOCKPREDICTION && /bin/bash run_weekly_update.sh >> logs/weekly.log 2>&1
```

创建 `run_daily_prediction.sh`:

```bash
#!/bin/bash
source venv/bin/activate

# 1. 更新数据（从 NeoTrade2）
cd /Users/mac/NeoTrade2
python3 scripts/fetcher_baostock.py --loop

# 2. 回到预测项目
cd /Users/mac/NeoTrade2/STOCKPREDICTION

# 3. 获取最新日期
DATE=$(date +%Y-%m-%d)

# 4. 增量生成标签
python scripts/backtest_labels.py --date $DATE

# 5. 增量计算特征
python scripts/compute_features.py --date $DATE

# 6. 收集筛选器特征
python scripts/collect_screener_scores.py --date $DATE

# 7. 运行预测
python scripts/predict.py --model models/xgboost_v1.0.json

echo "Prediction completed for $DATE"
```

## Dashboard 部署

### 启动 Dashboard

```bash
# 开发模式
cd dashboard
python app.py --port 5000

# 生产模式
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 配置 Cpolar 内网穿透（可选）

```bash
# 安装 cpolar
brew install cpolar

# 启动隧道
cpolar http 5000
```

## 监控

### 日志监控

```bash
# 查看最新日志
tail -f logs/prediction.log

# 查看错误日志
grep ERROR logs/*.log

# 查看今日预测
python -c "
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

date = datetime.now().strftime('%Y-%m-%d')
df = pd.read_sql(f\"SELECT * FROM predictions WHERE prediction_date = '{date}'\", 
                   sqlite3.connect('data/predictions.db'))
print(df.head(10).to_string())
"
```

### 性能监控

```bash
# 查看模型性能
python -c "
import sqlite3
import pandas as pd

df = pd.read_sql('''
    SELECT model_name, model_version, 
           precision, recall, f1_score, auc,
           created_at
    FROM model_performance
    ORDER BY created_at DESC
    LIMIT 10
''', sqlite3.connect('data/predictions.db'))
print(df.to_string())
"
```

### 数据健康检查

```bash
# 检查数据完整性
python scripts/data_health_check.py
```

## 故障排查

### 问题 1: 数据库锁定

**症状**: `sqlite3.OperationalError: database is locked`

**解决方案**:
```bash
# 查找占用进程
lsof data/*.db

# 结束进程
kill -9 <PID>

# 使用只读连接
conn = sqlite3.connect(db_path, timeout=60, uri=f"file:{db_path}?mode=ro")
```

### 问题 2: 内存不足

**症状**: `MemoryError` 或系统变慢

**解决方案**:
```python
# 分批处理
batch_size = 100
for i in range(0, len(data), batch_size):
    batch = data[i:i+batch_size]
    process_batch(batch)
    del batch
```

### 问题 3: 预测结果异常

**症状**: 概率全部接近 0 或 1

**检查步骤**:
1. 验证特征是否正确计算
2. 检查模型是否使用正确的版本
3. 确认输入数据格式正确

```bash
# 验证特征
python -c "
from scripts.compute_features import FeatureEngine
engine = FeatureEngine()
stats = engine.get_feature_stats()
print(stats)
"
```

## 备份与恢复

### 备份

```bash
# 创建备份目录
mkdir -p backups/$(date +%Y%m%d)

# 备份数据库
cp data/*.db backups/$(date +%Y%m%d)/

# 备份模型
cp models/*.json backups/$(date +%Y%m%d)/

# 备份代码
tar -czf backups/$(date +%Y%m%d)/code.tar.gz *.py scripts/ models/
```

### 恢复

```bash
# 选择备份日期
BACKUP_DATE=20260414

# 恢复数据库
cp backups/$BACKUP_DATE/*.db data/

# 恢复模型
cp backups/$BACKUP_DATE/*.json models/

# 恢复代码
tar -xzf backups/$BACKUP_DATE/code.tar.gz
```

## 安全建议

1. **数据库安全**
   - 使用只读连接读取 NeoTrade2 数据
   - 定期备份本地数据库
   - 不要在代码中硬编码敏感信息

2. **网络安全**
   - Dashboard 使用 Basic Auth 保护
   - 不要暴露 API 端口到公网
   - 使用 HTTPS（如需外网访问）

3. **数据安全**
   - 定期清理过期日志
   - 敏感数据加密存储
   - 设置适当的文件权限

## 更新升级

### 依赖更新

```bash
# 检查过期包
pip list --outdated

# 更新特定包
pip install --upgrade xgboost

# 更新所有包
pip list --outdated | awk 'NR>2 {print $1}' | xargs pip install --upgrade
```

### 代码更新

```bash
# 拉取最新代码
git pull origin main

# 重新安装依赖
pip install -r requirements.txt

# 重新初始化数据库（如需要）
python -c "from models.database import *; ..."
```

## 性能优化

### 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_stock_features_code_date ON stock_features(code, trade_date);
CREATE INDEX idx_screener_features_code_date ON screener_features(code, trade_date, screener_name);
CREATE INDEX idx_predictions_date ON predictions(prediction_date);

-- 分析查询计划
EXPLAIN QUERY PLAN SELECT * FROM stock_features WHERE code = '000001.SZ';
```

### 内存优化

```python
# 使用生成器处理大数据
def batch_generator(data, batch_size):
    for i in range(0, len(data), batch_size):
        yield data[i:i+batch_size]

for batch in batch_generator(large_data, 1000):
    process_batch(batch)
```

## 生产部署检查清单

- [ ] 虚拟环境已创建并激活
- [ ] 所有依赖已安装
- [ ] 数据库已初始化
- [ ] 历史数据已准备（标签、特征、筛选器）
- [ ] 模型已训练并保存
- [ ] Cron 任务已配置
- [ ] 日志目录已创建
- [ ] 备份策略已配置
- [ ] 监控已设置
- [ ] Dashboard 可正常访问
