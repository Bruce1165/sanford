"""
config.py – STOCKPREDICTION 项目配置中心

所有路径、常量、参数均在此处定义。
"""

from pathlib import Path

# ──────────────────────────────────────────────
# 项目路径
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"

# NeoTrade2 路径（只读）
NEOTRADE_ROOT = PROJECT_ROOT.parent
NEOTRADE_DB_PATH = NEOTRADE_ROOT / "data" / "stock_data.db"
NEOTRADE_SCREENERS_DIR = NEOTRADE_ROOT / "screeners"

# ──────────────────────────────────────────────
# 本地数据库路径
# ──────────────────────────────────────────────
LABELS_DB = DATA_DIR / "labels.db"
FEATURES_DB = DATA_DIR / "features.db"
SCREENER_SCORES_DB = DATA_DIR / "screener_scores.db"
PREDICTIONS_DB = DATA_DIR / "predictions.db"

# ──────────────────────────────────────────────
# 预测目标参数
# ──────────────────────────────────────────────
# 预测未来 21-34 个交易日内上涨 20%
TARGET_HORIZON_MIN = 21   # 最短持有天数
TARGET_HORIZON_MAX = 34   # 最长持有天数
TARGET_GAIN = 0.20        # 目标涨幅 20%

# ──────────────────────────────────────────────
# 标签生成参数
# ──────────────────────────────────────────────
LOOKBACK_DAYS = 30        # 用于计算特征的历史数据天数
MIN_HISTORY_DAYS = 30     # 股票最少需要的历史天数

# ──────────────────────────────────────────────
# 特征参数
# ──────────────────────────────────────────────
# 技术指标窗口
MA_WINDOWS = [5, 10, 20, 60]
EMA_WINDOWS = [12, 26]
RSI_WINDOW = 14
ATR_WINDOW = 14
BOLLINGER_WINDOW = 20
STOCHASTIC_K = 14
STOCHASTIC_D = 3

# ──────────────────────────────────────────────
# 筛选器列表（用作特征）
# ──────────────────────────────────────────────
SCREENER_FEATURES = [
    "coffee_cup_screener",
    "coffee_cup_handle_screener_v4",
    "jin_feng_huang_screener",
    "yin_feng_huang_screener",
    "shi_pan_xian_screener",
    "er_ban_hui_tiao_screener",
    "zhang_ting_bei_liang_yin_screener",
    "breakout_20day_screener",
    "breakout_main_screener",
    "daily_hot_cold_screener",
    "shuang_shou_ban_screener",
    "ashare_21_screener",
]

# ──────────────────────────────────────────────
# 模型参数
# ──────────────────────────────────────────────
TRAIN_TEST_SPLIT = 0.8    # 训练集比例（按时间分割）
CV_FOLDS = 5              # 交叉验证折数

# ──────────────────────────────────────────────
# 目录初始化
# ──────────────────────────────────────────────
for _d in (DATA_DIR, MODELS_DIR, LOGS_DIR, REPORTS_DIR,
           NOTEBOOKS_DIR, DASHBOARD_DIR):
    _d.mkdir(parents=True, exist_ok=True)
