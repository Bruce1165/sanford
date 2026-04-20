"""
config.py – 全局配置中心
所有路径、常量、过滤规则均在此处定义，其余脚本直接 import 使用。
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# ──────────────────────────────────────────────
# 工作区路径
# ──────────────────────────────────────────────
WORKSPACE      = Path(os.getenv('WORKSPACE_ROOT', str(Path(__file__).parent.parent)))
SCRIPTS_DIR    = WORKSPACE / "scripts"
DATA_DIR       = WORKSPACE / "data"
LOGS_DIR       = WORKSPACE / "logs"
BACKUP_DIR     = WORKSPACE / "backups"
CHECKPOINT_DIR = LOGS_DIR / "checkpoints"

DB_PATH        = DATA_DIR / "stock_data.db"

# ──────────────────────────────────────────────
# 日志配置
# ──────────────────────────────────────────────
LOG_MAX_BYTES    = 10 * 1024 * 1024   # 10 MB per file
LOG_BACKUP_COUNT = 30                  # 保留 30 个轮转文件
DB_BACKUP_COUNT  = 7                   # 保留 7 份 DB 备份

# ──────────────────────────────────────────────
# 下载日期范围
# ──────────────────────────────────────────────
DOWNLOAD_START_DATE = "2024-09-01"


def get_end_date() -> str:
    """返回今日日期字符串 YYYY-MM-DD（动态，无硬编码）。"""
    return date.today().strftime("%Y-%m-%d")


def get_end_date_compact() -> str:
    """返回今日日期字符串 YYYYMMDD（用于 AKShare 接口）。"""
    return date.today().strftime("%Y%m%d")


# ──────────────────────────────────────────────
# 限速参数
# ──────────────────────────────────────────────
RATE_LIMIT_DEFAULT        = 0.5
RATE_LIMIT_MIN_DELAY      = 0.2
RATE_LIMIT_MAX_DELAY      = 8.0
RATE_LIMIT_SUCCESS_FACTOR = 0.9
RATE_LIMIT_FAILURE_FACTOR = 1.5

# ──────────────────────────────────────────────
# 重试参数
# ──────────────────────────────────────────────
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY   = 1.0
RETRY_MAX_DELAY    = 60.0

# ──────────────────────────────────────────────
# 股票过滤规则
# ──────────────────────────────────────────────
# 深圳指数前缀（399xxx）
SZ_INDEX_PREFIXES = ("399",)

# 北交所前缀
BSE_PREFIXES = ("43", "83", "87", "88")

# 名称关键词排除
EXCLUDE_NAME_KEYWORDS = (
    "指数", "ETF", "LOF", "REITs", "REIT", "退", "可转债",
)

# ST 关键词
ST_KEYWORDS = ("*ST", "ST", "PT")

# ──────────────────────────────────────────────
# 市值过滤（单位：元）
# ──────────────────────────────────────────────
# 流通市值过滤（临时禁用用于测试）
MARKET_CAP_MIN = 0     * 1e8    #  0 亿元（禁用下限）
MARKET_CAP_MAX = 1e16          # 无上限（禁用上限）

# stocks 表中 circulating_market_cap 为 None 时的处理策略：
#   'include'  → 没有市值数据的股票照样保留（保守）
#   'exclude'  → 没有市值数据的股票直接排除（严格）
MARKET_CAP_MISSING_POLICY = "include"

# ──────────────────────────────────────────────
# 数据完整性
# ──────────────────────────────────────────────
MIN_DATA_DAYS = 100

# ──────────────────────────────────────────────
# 交易日历缓存
# ──────────────────────────────────────────────
CALENDAR_REFRESH_DAYS = 7

# ──────────────────────────────────────────────
# macOS 通知
# ──────────────────────────────────────────────
ENABLE_NOTIFICATIONS = True

# ──────────────────────────────────────────────
# 运行历史 / 状态文件
# ──────────────────────────────────────────────
RUN_HISTORY_FILE        = LOGS_DIR / "run_history.json"
RUN_HISTORY_MAX_ENTRIES = 90
STATUS_FILE             = LOGS_DIR / "last_run_status.json"

# ──────────────────────────────────────────────
# Baostock 参数
# ──────────────────────────────────────────────
BAOSTOCK_DAILY_FIELDS = (
    "date,code,open,high,low,close,preclose,volume,amount,"
    "adjustflag,turn,tradestatus,pctChg,isST"
)
BAOSTOCK_ADJUST = "2"   # 后复权

# ──────────────────────────────────────────────
# AKShare 参数
# ──────────────────────────────────────────────
AKSHARE_ADJUST = "hfq"   # 后复权

# ──────────────────────────────────────────────
# 子进程超时（秒）
# ──────────────────────────────────────────────
STEP_TIMEOUT = 600

# ──────────────────────────────────────────────
# Flask Dashboard 端口
# ──────────────────────────────────────────────
FLASK_PORT = int(os.getenv("FLASK_PORT", "8765"))

# ──────────────────────────────────────────────
# 目录初始化
# ──────────────────────────────────────────────
for _d in (DATA_DIR, LOGS_DIR, BACKUP_DIR, CHECKPOINT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
