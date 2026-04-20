# Neo股票数据分析系统 - 数据管道文档

> **版本**: 1.0  
> **更新日期**: 2026-03-19  
> **维护者**: Technical Writer  

---

## 1. 系统架构概览

### 1.1 数据流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Neo股票数据分析系统                                │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐         ┌──────────────┐         ┌──────────────────────┐
  │   Baostock   │ ──────> │   数据管道    │ ──────> │    SQLite数据库       │
  │   数据源      │         │   ETL处理    │         │   stock_data.db      │
  └──────────────┘         └──────────────┘         └──────────┬───────────┘
       │                                                       │
       │                                                       │
       ▼                                                       ▼
  ┌──────────────┐         ┌──────────────┐         ┌──────────────────────┐
  │  A股全量数据  │         │  数据清洗/   │         │   11个筛选器引擎      │
  │  4663只股票   │         │  去重/验证   │         │   技术分析计算        │
  └──────────────┘         └──────────────┘         └──────────┬───────────┘
                                                                │
                                                                ▼
  ┌──────────────┐         ┌──────────────┐         ┌──────────────────────┐
  │   图表生成    │ <────── │  筛选结果输出 │ <────── │   Excel/JSON文件     │
  │  K线/形态图   │         │  多维度分析   │         │   数据/screeners/    │
  └──────────────┘         └──────────────┘         └──────────┬───────────┘
                                                                │
                                                                ▼
                                                       ┌──────────────────────┐
                                                       │   Flask Dashboard    │
                                                       │   Web可视化界面      │
                                                       │   Port: 5003         │
                                                       └──────────────────────┘
```

### 1.2 核心组件说明

| 组件 | 职责 | 技术栈 |
|------|------|--------|
| **Baostock** | A股历史数据供应商 | baostock库 |
| **数据管道** | ETL处理、增量更新、断点续传 | Python + SQLite |
| **筛选器引擎** | 11种技术分析形态识别 | Python + pandas |
| **Dashboard** | Web可视化、API服务 | Flask + SQLite |

---

## 2. 数据存储结构

### 2.1 数据库 Schema

```sql
-- 股票基础信息表
CREATE TABLE stocks (
    code TEXT PRIMARY KEY,      -- 股票代码 (如: 600519)
    name TEXT,                  -- 股票名称 (如: 贵州茅台)
    industry TEXT,              -- 所属行业
    list_date TEXT             -- 上市日期
);

-- 日行情数据表 (核心数据)
CREATE TABLE daily_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,         -- 股票代码
    trade_date TEXT NOT NULL,   -- 交易日期 (YYYY-MM-DD)
    open REAL,                  -- 开盘价
    high REAL,                  -- 最高价
    low REAL,                   -- 最低价
    close REAL,                 -- 收盘价
    preclose REAL,              -- 昨收价
    volume INTEGER,             -- 成交量(股)
    amount REAL,                -- 成交额(元)
    turnover REAL,              -- 换手率(%)
    pct_change REAL,            -- 涨跌幅(%)
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, trade_date)    -- 唯一约束防重复
);

-- Dashboard运行记录表
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screener_name TEXT NOT NULL,
    run_date TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'running',
    stocks_found INTEGER DEFAULT 0,
    error_message TEXT
);
```

### 2.2 数据目录结构

```
data/
├── stock_data.db              # 主数据库 (约326MB)
├── daily_update_progress_v2.json  # 每日更新进度
├── download_progress.json     # 历史数据下载进度
├── screeners/                 # 筛选器输出目录
│   ├── coffee_cup/           # 咖啡杯形态结果
│   │   ├── 2026-03-13.xlsx
│   │   └── charts/
│   ├── jin_feng_huang/       # 金凤凰形态结果
│   ├── er_ban_hui_tiao/      # 二板回调结果
│   ├── zhang_ting_bei_liang_yin/  # 涨停倍量阴结果
│   ├── yin_feng_huang/       # 银凤凰形态结果
│   ├── shi_pan_xian/         # 试盘线形态结果
│   ├── breakout_20day/       # 20日突破结果
│   ├── breakout_main/        # 主升突破结果
│   ├── ascending_triangle/   # 上升三角形结果
│   ├── double_bottom/        # 双底形态结果
│   ├── flat_base/            # 平底形态结果
│   └── high_tight_flag/      # 高紧旗形结果
├── progress/                 # 各筛选器进度文件
├── news_cache/               # 新闻缓存(24小时)
└── llm_cache/                # LLM分析缓存
```

---

## 3. 每日更新流程

### 3.1 标准流程图

```
每日08:30自动启动
        │
        ▼
┌───────────────┐
│ 1. 检查交易日 │ ── 周末/节假日跳过
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 2. 加载进度   │ ── 读取daily_update_progress_v2.json
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 3. 批量下载   │ ── 每批100只，断点续传
│   Baostock    │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 4. 数据入库   │ ── INSERT OR REPLACE幂等写入
│   SQLite      │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 5. 更新进度   │ ── 标记已完成股票
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 6. 循环检查   │ ── 未完成则回到步骤3
│   是否完成    │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 7. 执行筛选器 │ ── 运行11个筛选器
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ 8. 生成报告   │ ── Excel + 图表输出
└───────────────┘
```

### 3.2 关键脚本说明

#### `daily_update_screener.py` - 每日数据更新主程序

**功能**: 从Baostock下载前一日行情数据，支持断点续传

**核心特性**:
- **小批量处理**: 每批100只股票，避免内存溢出
- **断点续传**: 通过 `daily_update_progress_v2.json` 记录进度
- **幂等写入**: 使用 `INSERT OR REPLACE` 防止重复数据
- **退市识别**: 连续3次失败标记为退市股，跳过处理

**进度文件结构**:
```json
{
  "completed": ["600519", "000001", ...],  // 已完成股票列表(去重)
  "failed": {"600000": 1, ...},            // 失败次数记录
  "target_date": "2026-03-18",             // 目标日期
  "status": "running",                     // running/completed
  "last_updated": "2026-03-19T08:35:00"
}
```

**使用方式**:
```bash
# 单次运行(处理一批100只)
python3 scripts/daily_update_screener.py

# 指定日期
python3 scripts/daily_update_screener.py --date 2026-03-18

# 循环运行直到完成
python3 scripts/daily_update_screener.py --loop
```

---

#### `download_chunked.py` - 历史数据补录程序

**功能**: 批量下载历史数据，用于初始化或补录缺失数据

**核心特性**:
- **分块下载**: 每块200只股票
- **断点续传**: 通过 `download_progress.json` 记录
- **缺失检测**: 自动识别数据不足300天的股票

**进度文件结构**:
```json
{
  "completed": ["600519", ...],  // 已完成
  "failed": ["000001", ...],     // 失败列表
  "last_chunk": 5,               // 最后处理的块号
  "last_update": "2026-03-19T09:00:00"
}
```

**使用方式**:
```bash
python3 download_chunked.py
```

**数据范围**: 2024-09-01 至 运行当日

---

## 4. 错误处理和恢复流程

### 4.1 常见错误类型

| 错误类型 | 症状 | 处理方案 |
|---------|------|---------|
| **网络超时** | Baostock连接失败 | 自动重试3次，间隔5秒 |
| **数据重复** | IntegrityError | INSERT OR REPLACE自动处理 |
| **退市股票** | 连续无数据 | 标记完成，记录到failed |
| **内存不足** | 批量处理中断 | 减小BATCH_SIZE后重试 |
| **登录失败** | bs.login()失败 | 检查网络，10分钟后重试 |

### 4.2 数据修复流程

#### 场景1: 某日数据缺失

```bash
# 1. 检查缺失情况
python3 scripts/check_integrity.py --date 2026-03-18

# 2. 重新下载指定日期
python3 scripts/daily_update_screener.py --date 2026-03-18 --loop

# 3. 验证修复结果
python3 scripts/check_integrity.py --date 2026-03-18
```

#### 场景2: 进度文件损坏

```bash
# 1. 备份损坏文件
mv data/daily_update_progress_v2.json data/daily_update_progress_v2.json.bak

# 2. 重建进度(已有数据视为已完成)
python3 -c "
import json
from datetime import datetime
progress = {
    'completed': [],  # 会从数据库自动识别已有数据
    'failed': {},
    'target_date': '2026-03-18',
    'status': 'running',
    'last_updated': datetime.now().isoformat()
}
with open('data/daily_update_progress_v2.json', 'w') as f:
    json.dump(progress, f, indent=2)
"

# 3. 重新运行
python3 scripts/daily_update_screener.py --loop
```

#### 场景3: 数据库损坏

```bash
# 1. 备份当前数据库
cp data/stock_data.db data/stock_data.db.bak.$(date +%Y%m%d)

# 2. 使用SQLite修复
sqlite3 data/stock_data.db ".mode insert" ".dump" > data/recovery.sql
sqlite3 data/stock_data.db.new < data/recovery.sql

# 3. 验证并替换
mv data/stock_data.db.new data/stock_data.db
```

### 4.3 紧急回滚流程

```bash
# 1. 停止所有运行中的任务
pkill -f "daily_update_screener.py"
pkill -f "run_all_screeners.py"

# 2. 恢复数据库到备份版本
cp data/stock_data.db.bak.20260318 data/stock_data.db

# 3. 清理当日进度文件
rm data/daily_update_progress_v2.json

# 4. 重新执行当日更新
python3 scripts/daily_update_screener.py --date 2026-03-18 --loop
```

---

## 5. 性能指标

### 5.1 数据规模

| 指标 | 数值 | 说明 |
|------|------|------|
| 股票总数 | 4,663只 | A股全量(剔除退市) |
| 数据时间跨度 | 2024-09-01 至今 | 约6个月 |
| 日数据记录 | ~1,400万条 | 4663 × 300天 |
| 数据库大小 | ~326MB | stock_data.db |

### 5.2 处理性能

| 任务 | 耗时 | 频率 |
|------|------|------|
| 每日数据更新 | ~20分钟 | 每日08:30 |
| 全量筛选器运行 | ~15分钟 | 数据更新后 |
| 单筛选器运行 | ~1-3分钟 | 按需执行 |
| 图表生成 | ~5分钟 | 筛选后执行 |

### 5.3 数据新鲜度要求

- **目标**: T+1 (前一日收盘后数据)
- **最大延迟**: < 24小时
- **监控告警**: 数据延迟超过12小时触发

---

## 6. 附录

### 6.1 相关文件索引

| 文件路径 | 说明 |
|---------|------|
| `scripts/daily_update_screener.py` | 每日更新主程序 |
| `download_chunked.py` | 历史数据下载 |
| `scripts/fetcher_baostock.py` | Baostock数据获取器 |
| `scripts/database.py` | 数据库ORM模型 |
| `data/stock_data.db` | 主数据库文件 |
| `data/daily_update_progress_v2.json` | 每日更新进度 |

### 6.2 联系方式

- **紧急联系人**: Bruce
- **技术支持**: Neo Agent Team
- **数据问题**: Data Engineer Agent
