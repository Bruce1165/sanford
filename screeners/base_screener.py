from __future__ import annotations
import os
"""
base_screener.py – 所有选股器的抽象基类

修复记录
--------
* [BUG-FIX] 原代码错误排除深圳主板 000xxx，现已修正
* [BUG-FIX] daily_prices 换手率字段名 turn → turnover（与 schema 一致）
* [FEATURE]  StockFilter 新增流通市值过滤（30亿～1500亿）
* [IMPROVEMENT] current_date 从 DB MAX(trade_date) 动态获取
"""


import abc
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sys
import os
# Get workspace root and add scripts directory to path
if 'WORKSPACE_ROOT' in os.environ:
    workspace_root = Path(os.environ['WORKSPACE_ROOT'])
else:
    workspace_root = Path(__file__).parent.parent  # Go up two levels: screeners/ -> root

sys.path.insert(0, str(workspace_root))
sys.path.insert(0, str(workspace_root / 'scripts'))
sys.path.insert(0, str(workspace_root / 'backend'))

# Now import from config (should work from workspace_root/scripts/)
from config import (
    DB_PATH,
    SZ_INDEX_PREFIXES,
    BSE_PREFIXES,
    EXCLUDE_NAME_KEYWORDS,
    ST_KEYWORDS,
    MARKET_CAP_MIN,
    MARKET_CAP_MAX,
    MARKET_CAP_MISSING_POLICY,
    DATA_DIR,
)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# 数据类
# ────────────────────────────────────────────────────────────────────────────
@dataclass
class StockInfo:
    code: str
    name: str
    is_delisted: bool = False
    last_trade_date: Optional[str] = None
    circulating_market_cap: Optional[float] = None   # 流通市值（元）
    total_market_cap: Optional[float] = None          # 总市值（元）


@dataclass
class DailyPrice:
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0
    pct_change: float = 0.0
    turnover: float = 0.0     # 换手率（与 daily_prices.turnover 一致）


@dataclass
class ScreenResult:
    code: str
    name: str
    score: float = 0.0
    reason: str = ""
    extra: Dict = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────
# 股票过滤器
# ────────────────────────────────────────────────────────────────────────────
class StockFilter:
    """
    集中式 A 股过滤逻辑。

    排除规则（按序应用）：
    1. 已退市
    2. 深圳指数（399xxx）
    3. 北交所（43/83/87/88 前缀）
    4. 名称含指数/ETF/LOF/REITs/退 等关键词
    5. 名称含 ST / *ST / PT
    6. 流通市值不在 [MARKET_CAP_MIN, MARKET_CAP_MAX] 区间
       （MARKET_CAP_MISSING_POLICY 控制缺失值行为）
    """

    @staticmethod
    def is_valid_stock(
        code: str,
        name: str,
        is_delisted: bool = False,
        circulating_market_cap: Optional[float] = None,
    ) -> bool:
        # 1. 退市
        if is_delisted:
            return False

        # 2. 深圳指数（399xxx）
        if code.startswith(SZ_INDEX_PREFIXES):
            return False

        # 3. 北交所
        if code.startswith(BSE_PREFIXES):
            return False

        # 4. 名称关键词
        for kw in EXCLUDE_NAME_KEYWORDS:
            if name is None or kw in name:
                return False

        # 5. ST / *ST / PT
        if name is None:
            return False
        name_upper = name.upper()
        for st in ST_KEYWORDS:
            if st.upper() in name_upper:
                return False

        # 6. 流通市值过滤
        if circulating_market_cap is None:
            # 按策略处理缺失值
            if MARKET_CAP_MISSING_POLICY == "exclude":
                return False
            # 'include'：暂时放行，等市值同步后再过滤
        else:
            if not (MARKET_CAP_MIN <= circulating_market_cap <= MARKET_CAP_MAX):
                return False

        return True

    @classmethod
    def filter_stocks(cls, stocks: List[StockInfo]) -> List[StockInfo]:
        valid = [
            s for s in stocks
            if cls.is_valid_stock(
                s.code,
                s.name,
                s.is_delisted,
                s.circulating_market_cap,
            )
        ]
        logger.debug(
            "股票过滤：输入 %d 只，保留 %d 只（市值区间 %.0f亿～%.0f亿）",
            len(stocks), len(valid),
            MARKET_CAP_MIN / 1e8, MARKET_CAP_MAX / 1e8,
        )
        return valid

    @classmethod
    def get_exclusion_reason(
        cls,
        code: str,
        name: str,
        is_delisted: bool = False,
        circulating_market_cap: Optional[float] = None,
    ) -> Optional[str]:
        """返回过滤原因，若股票合法则返回 None。副作用：方便调用方显示拒绝原因。"""
        if is_delisted:
            return "已退市"
        if code.startswith(SZ_INDEX_PREFIXES):
            return "深圳指数"
        if code.startswith(BSE_PREFIXES):
            return "北交所股票"
        name_upper = name.upper()
        for kw in EXCLUDE_NAME_KEYWORDS:
            if kw in name:
                return f"名称包含关键词[{kw}]"
        for st in ST_KEYWORDS:
            if st.upper() in name_upper:
                return f"ST/退市股票"
        if circulating_market_cap is None:
            if MARKET_CAP_MISSING_POLICY == "exclude":
                return "无流通市值数据"
        else:
            if not (MARKET_CAP_MIN <= circulating_market_cap <= MARKET_CAP_MAX):
                cap_b = circulating_market_cap / 1e8
                return f"流通市值{cap_b:.1f}亿不在[{MARKET_CAP_MIN/1e8:.0f}亿, {MARKET_CAP_MAX/1e8:.0f}亿]区间"
        return None


# ────────────────────────────────────────────────────────────────────────────
# 数据库 Mixin
# ────────────────────────────────────────────────────────────────────────────
class DBMixin:
    _db_path: Path = DB_PATH

    def get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def get_all_stocks(self) -> List[StockInfo]:
        """从 stocks 表读取所有股票（含市值），并应用过滤规则。"""
        with self.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT code, name,
                       COALESCE(is_delisted, 0)          AS is_delisted,
                       last_trade_date,
                       circulating_market_cap,
                       total_market_cap
                FROM   stocks
                ORDER  BY code
                """
            ).fetchall()

        raw = [
            StockInfo(
                code=r["code"],
                name=r["name"],
                is_delisted=bool(r["is_delisted"]),
                last_trade_date=r["last_trade_date"],
                circulating_market_cap=r["circulating_market_cap"],
                total_market_cap=r["total_market_cap"],
            )
            for r in rows
        ]
        return StockFilter.filter_stocks(raw)

    def get_latest_data_date(self) -> Optional[date]:
        """从 daily_prices 表查询最新 trade_date，消除硬编码日期。"""
        try:
            with self.get_conn() as conn:
                row = conn.execute(
                    "SELECT MAX(trade_date) AS dt FROM daily_prices"
                ).fetchone()
            if row and row["dt"]:
                return datetime.strptime(row["dt"], "%Y-%m-%d").date()
        except Exception as exc:
            logger.warning("查询最新数据日期失败: %s", exc)
        return None

    def get_daily_prices(
        self,
        code: str,
        start_date: str,
        end_date: str,
        limit: int = 0,
    ) -> List[DailyPrice]:
        sql = """
            SELECT trade_date, open, high, low, close, volume,
                   COALESCE(amount,    0.0) AS amount,
                   COALESCE(pct_change, 0.0) AS pct_change,
                   COALESCE(turnover,  0.0) AS turnover
            FROM   daily_prices
            WHERE  code = ?
              AND  trade_date BETWEEN ? AND ?
            ORDER  BY trade_date ASC
        """
        if limit > 0:
            sql += f" LIMIT {limit}"
        try:
            with self.get_conn() as conn:
                rows = conn.execute(sql, (code, start_date, end_date)).fetchall()
            return [
                DailyPrice(
                    trade_date=r["trade_date"],
                    open=float(r["open"] or 0),
                    high=float(r["high"] or 0),
                    low=float(r["low"] or 0),
                    close=float(r["close"] or 0),
                    volume=float(r["volume"] or 0),
                    amount=float(r["amount"]),
                    pct_change=float(r["pct_change"]),
                    turnover=float(r["turnover"]),
                )
                for r in rows
            ]
        except Exception as exc:
            logger.warning("获取 %s 日线数据失败: %s", code, exc)
            return []

    def get_latest_n_prices(self, code: str, n: int) -> List[DailyPrice]:
        sql = """
            SELECT trade_date, open, high, low, close, volume,
                   COALESCE(amount,    0.0) AS amount,
                   COALESCE(pct_change, 0.0) AS pct_change,
                   COALESCE(turnover,  0.0) AS turnover
            FROM   daily_prices
            WHERE  code = ?
            ORDER  BY trade_date DESC
            LIMIT  ?
        """
        try:
            with self.get_conn() as conn:
                rows = conn.execute(sql, (code, n)).fetchall()
            return list(reversed([
                DailyPrice(
                    trade_date=r["trade_date"],
                    open=float(r["open"] or 0),
                    high=float(r["high"] or 0),
                    low=float(r["low"] or 0),
                    close=float(r["close"] or 0),
                    volume=float(r["volume"] or 0),
                    amount=float(r["amount"]),
                    pct_change=float(r["pct_change"]),
                    turnover=float(r["turnover"]),
                )
                for r in rows
            ]))
        except Exception as exc:
            logger.warning("获取 %s 最新 %d 条失败: %s", code, n, exc)
            return []

    def get_data_count(self, code: str) -> int:
        try:
            with self.get_conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM daily_prices WHERE code=?", (code,)
                ).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0


# ────────────────────────────────────────────────────────────────────────────
# 抽象基类
# ────────────────────────────────────────────────────────────────────────────
class BaseScreener(DBMixin, abc.ABC):
    """
    所有 A 股选股器的抽象基类（v2）。

    变更记录
    --------
    * [FIX] __init__ 接受 screener_name / db_path / enable_* 参数，兼容所有子类
    * [FIX] screen_stock 签名改为 (code, name) → Optional[Dict]，与子类实现对齐
    * [ADD] get_stock_data(code, days) → pd.DataFrame  供子类直接使用
    * [ADD] check_data_availability(date_str) → bool
    * [ADD] save_results(results, analysis_data, column_mapping) → str (Excel 路径)
    * [ADD] progress_tracker / news_fetcher 桩属性（保持接口兼容，功能未启用）
    * [KEEP] run() / run_and_save() 保留供旧架构兼容
    """

    screener_name: str = "BaseScreener"
    min_data_bars: int = 60
    lookback_days: int = 120

    def __init__(
        self,
        screener_name: Optional[str] = None,
        db_path: Optional[str] = None,
        enable_news: bool = False,
        enable_llm: bool = False,
        enable_progress: bool = False,
        **kwargs,  # 向后兼容：吸收子类传来的任意额外参数，永不崩溃
    ) -> None:
        if screener_name:
            self.screener_name = screener_name
        if db_path:
            self._db_path = Path(db_path).resolve()
        self._current_date: Optional[date] = None
        # 桩属性：保持子类引用兼容，功能未启用
        self.progress_tracker = None
        self.news_fetcher = None

        # 加载配置
        self._config: Optional[Dict] = None
        self._load_config()
        self._apply_config_parameters()

    # ── 配置管理 ──────────────────────────────────────────────────────────────

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """
        返回筛选器的参数Schema，子类应重写此方法。

        Schema格式:
        {
            'param_name': {
                'type': 'int' | 'float' | 'bool' | 'string',
                'default': default_value,
                'min': min_value,      # 可选，仅数值类型
                'max': max_value,      # 可选，仅数值类型
                'step': step_value,    # 可选，仅数值类型
                'display_name': '显示名称',
                'description': '参数描述',
                'group': '分组名称'     # 可选
            }
        }
        """
        return {}

    def _get_default_config(self) -> Dict:
        """获取默认配置（从子类属性或Schema生成）"""
        config = {
            'display_name': self.screener_name.replace('_', ' ').title(),
            'description': '',
            'category': '未分类',
            'parameters': {}
        }

        # 从Schema生成默认参数
        schema = self.get_parameter_schema()
        for param_name, param_schema in schema.items():
            config['parameters'][param_name] = {
                'value': param_schema.get('default'),
                'display_name': param_schema.get('display_name', param_name),
                'description': param_schema.get('description', ''),
                'group': param_schema.get('group', '其他'),
                'type': param_schema.get('type', 'string')
            }
            # 添加范围信息（如果有）
            if 'min' in param_schema:
                config['parameters'][param_name]['min'] = param_schema['min']
            if 'max' in param_schema:
                config['parameters'][param_name]['max'] = param_schema['max']
            if 'step' in param_schema:
                config['parameters'][param_name]['step'] = param_schema['step']
            if 'default' in param_schema:
                config['parameters'][param_name]['default'] = param_schema['default']

        return config

    def _load_config(self) -> None:
        """从JSON文件或数据库加载配置"""
        try:
            # 尝试从backend的config_loader导入
            from backend.config_loader import ConfigLoader
            self._config = ConfigLoader.load_config(self.screener_name, prefer_database=True)
        except ImportError:
            # 如果config_loader不可用，尝试从JSON文件加载
            self._config = self._load_config_from_file()

        # 如果没有找到配置，使用默认配置
        if self._config is None:
            self._config = self._get_default_config()

    def _load_config_from_file(self) -> Optional[Dict]:
        """从JSON配置文件加载"""
        config_dir = DATA_DIR / 'config' / 'screeners'
        config_file = config_dir / f'{self.screener_name}.json'

        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("[%s] 加载配置文件失败: %s", self.screener_name, exc)

        return None

    def _apply_config_parameters(self) -> None:
        """将配置参数应用到实例变量"""
        if not self._config or 'parameters' not in self._config:
            return

        parameters = self._config['parameters']

        # 应用常见参数（子类可以根据需要扩展）
        for param_name, param_config in parameters.items():
            value = param_config.get('value')
            if value is None:
                continue

            # 自动设置实例属性
            if hasattr(self, param_name):
                setattr(self, param_name, value)
                logger.debug("[%s] 应用配置参数: %s = %s", self.screener_name, param_name, value)

    def get_config(self) -> Dict:
        """获取当前配置"""
        if self._config is None:
            self._load_config()
        return self._config.copy() if self._config else {}

    def get_parameter_value(self, param_name: str, default=None):
        """获取参数值"""
        if not self._config or 'parameters' not in self._config:
            return default

        param_config = self._config['parameters'].get(param_name)
        if param_config:
            return param_config.get('value', default)

        return default

    # ── 日期属性 ──────────────────────────────────────────────────────────────

    @property
    def current_date(self) -> str:
        """返回 YYYY-MM-DD 字符串；子类可直接赋值 self.current_date = '2026-01-01'。"""
        if self._current_date is None:
            dt = self.get_latest_data_date() or date.today()
            self._current_date = dt
        if isinstance(self._current_date, date):
            return self._current_date.strftime("%Y-%m-%d")
        return str(self._current_date)[:10]

    @current_date.setter
    def current_date(self, value: str) -> None:
        """允许子类用字符串直接设置日期：self.current_date = '2026-03-26'"""
        if isinstance(value, str):
            try:
                dt = datetime.strptime(value[:10], "%Y-%m-%d").date()
            except ValueError:
                dt = date.today()
        elif isinstance(value, date):
            dt = value
        else:
            dt = date.today()

        # 如果不是交易日，自动调整为最近的交易日
        try:
            from trading_calendar import is_trading_day, get_recent_trading_day
            if not is_trading_day(dt):
                corrected = get_recent_trading_day(dt)
                logger.warning(
                    "[%s] %s 不是交易日，自动调整为 %s",
                    self.screener_name, dt, corrected
                )
                dt = corrected
        except Exception as exc:
            logger.warning("[%s] 交易日历检查失败: %s", self.screener_name, exc)

        self._current_date = dt

    # ── 数据便利方法 ──────────────────────────────────────────────────────────

    def get_stock_data(self, code: str, days: int = 120) -> Optional["pd.DataFrame"]:
        """
        返回近 days 条日线数据 DataFrame（按日期升序）。
        列：trade_date(datetime64), open, high, low, close, volume, amount, turnover, pct_change
        """
        import pandas as pd
        sql = """
            SELECT dp.trade_date, dp.open, dp.high, dp.low, dp.close,
                   dp.volume, COALESCE(dp.amount, 0) AS amount,
                   COALESCE(dp.turnover, 0) AS turnover,
                   COALESCE(dp.pct_change, 0) AS pct_change
            FROM daily_prices dp
            WHERE dp.code = ?
              AND dp.trade_date <= ?
            ORDER BY dp.trade_date DESC
            LIMIT ?
        """
        try:
            with self.get_conn() as conn:
                df = pd.read_sql_query(
                    sql, conn,
                    params=(code, self.current_date, days),
                )
        except Exception as exc:
            logger.debug("get_stock_data(%s) 失败: %s", code, exc)
            return None

        if df.empty:
            return None

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.sort_values("trade_date").reset_index(drop=True)
        df["code"] = code
        return df

    def check_data_availability(self, check_date: str) -> bool:
        """检查数据库中是否存在 check_date 当天或之前的数据，并且 check_date 是交易日。"""
        # 检查是否是交易日
        try:
            from trading_calendar import is_trading_day
            check_dt = datetime.strptime(check_date[:10], "%Y-%m-%d").date()
            if not is_trading_day(check_dt):
                logger.warning(
                    "[%s] %s 不是交易日，无法进行筛选",
                    self.screener_name, check_dt
                )
                return False
        except ValueError:
            return False
        except Exception as exc:
            logger.warning("[%s] 交易日检查失败: %s", self.screener_name, exc)

        # 原有检查：DB 最新日期是否 >= 指定日期
        try:
            with self.get_conn() as conn:
                row = conn.execute(
                    "SELECT MAX(trade_date) FROM daily_prices"
                ).fetchone()
            if not row or not row[0]:
                return False
            return str(row[0])[:10] >= check_date[:10]
        except Exception as exc:
            logger.warning("check_data_availability 失败: %s", exc)
            return False

    def save_results(
        self,
        results: List[Dict],
        analysis_data: Optional[Dict] = None,
        column_mapping: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        将结果列表保存为 Excel 文件。
        路径：DATA_DIR/screeners/{screener_name}/{current_date}.xlsx
        返回：保存路径字符串
        """
        import pandas as pd
        from config import DATA_DIR

        if not results:
            logger.warning("[%s] save_results: 无数据，跳过保存", self.screener_name)
            return ""

        out_dir = Path(DATA_DIR) / "screeners" / self.screener_name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{self.current_date}.xlsx"

        df = pd.DataFrame(results)

        # 按 column_mapping 重命名列（只处理存在的列）
        if column_mapping:
            rename = {k: v for k, v in column_mapping.items() if k in df.columns}
            df = df.rename(columns=rename)
            # 按 mapping value 顺序排列列
            ordered = [v for v in column_mapping.values() if v in df.columns]
            rest = [c for c in df.columns if c not in ordered]
            df = df[ordered + rest]

        try:
            df.to_excel(str(out_path), index=False, engine="xlsxwriter")
            logger.info("[%s] 结果已保存: %s", self.screener_name, out_path)
        except Exception as exc:
            logger.warning("[%s] 保存 Excel 失败，改用 openpyxl: %s", self.screener_name, exc)
            df.to_excel(str(out_path), index=False)

        return str(out_path)

    # ── 抽象方法（新签名） ────────────────────────────────────────────────────

    @abc.abstractmethod
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """对单只股票执行选股逻辑，命中返回 dict，否则返回 None。"""

    # ── 保留旧 run() 供兼容 ───────────────────────────────────────────────────

    def run(self) -> Tuple[List[ScreenResult], Dict]:
        """旧接口保留，内部调用 screen_stock(code, name)。"""
        cur = self.current_date
        logger.info("[%s] 开始选股，基准日期=%s", self.screener_name, cur)

        stocks = self.get_all_stocks()
        logger.info("[%s] 过滤后有效股票数: %d", self.screener_name, len(stocks))

        results_raw: List[ScreenResult] = []
        processed = skipped_data = errors = 0

        for stock in stocks:
            try:
                raw = self.screen_stock(stock.code, stock.name)
                if raw is not None:
                    results_raw.append(
                        ScreenResult(
                            code=stock.code,
                            name=stock.name,
                            score=raw.get("score", 0.0),
                            reason=raw.get("reason", ""),
                            extra={k: v for k, v in raw.items()
                                   if k not in ("code", "name", "score", "reason")},
                        )
                    )
                processed += 1
            except Exception as exc:
                logger.warning("[%s] 处理 %s 异常: %s", self.screener_name, stock.code, exc)
                errors += 1

        summary = {
            "screener": self.screener_name,
            "date": cur,
            "total_stocks": len(stocks),
            "processed": processed,
            "skipped_no_data": skipped_data,
            "errors": errors,
            "hits": len(results_raw),
        }
        logger.info(
            "[%s] 选股完成: 命中=%d / 处理=%d / 错误=%d",
            self.screener_name, len(results_raw), processed, errors,
        )
        return results_raw, summary

    def run_and_save(self, output_path: Optional[Path] = None) -> Tuple[List[ScreenResult], Dict]:
        import json
        results, summary = self.run()
        if output_path is None:
            from config import LOGS_DIR
            output_path = LOGS_DIR / f"{self.screener_name}_{self.current_date}.json"
        payload = {
            "summary": summary,
            "results": [
                {"code": r.code, "name": r.name, "score": r.score,
                 "reason": r.reason, **r.extra}
                for r in results
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("[%s] 结果已保存至 %s", self.screener_name, output_path)
        return results, summary
