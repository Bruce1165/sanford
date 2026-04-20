# 筛选器交易日检查缺失问题分析

## 问题描述

所有筛选器（15个）都没有对"当前日期是否是交易日"进行检查。当用户指定或系统使用非交易日的日期时，筛选器会产生错误结果。

---

## 复现步骤

### 测试环境
- **当前日期**：2026-04-07（周一，交易日）
- **昨天**：2026-04-06（周日，非交易日）
- **前天**：2026-04-05（周六，非交易日）

### 问题场景

#### 场景1：用户手动指定非交易日
```bash
# 用户错误地指定了昨天的日期（周日）
python3 screeners/er_ban_hui_tiao_screener.py --date 2026-04-06
```

**实际发生的情况：**
1. 筛选器将 `current_date` 设置为 `2026-04-06`
2. `get_stock_data()` 执行 SQL：
   ```sql
   SELECT * FROM daily_prices
   WHERE code = ? AND trade_date <= '2026-04-06'
   ORDER BY trade_date DESC
   LIMIT 34
   ```
3. 由于 4月5日（周六）和4月6日（周日）都不是交易日，DB中没有这些日期的数据
4. 查询返回的数据截止到 `2026-04-03` 或更早
5. 筛选器基于这些旧数据进行筛选逻辑，导致结果不正确

#### 场景2：数据同步后立即运行
- 周五（4月4日）收盘后同步数据
- 周末（4月5-6日）无数据更新
- 如果使用 `date.today()` 作为当前日期，可能获取到周末日期

---

## 受影响的筛选器

所有15个筛选器都可能受影响：

| 筛选器 | 文件 |
|--------|------|
| 上升三角形筛选器 | `ascending_triangle_screener.py` |
| A股21选 | `ashare_21_screener.py` |
| 20日突破 | `breakout_20day_screener.py` |
| 主升浪突破 | `breakout_main_screener.py` |
| 杯柄形态 | `coffee_cup_screener.py` |
| 每日冷热榜 | `daily_hot_cold_screener.py` |
| 双底形态 | `double_bottom_screener.py` |
| **二板回调** | **`er_ban_hui_tiao_screener.py`** |
| 平底形态 | `flat_base_screener.py` |
| 高位旗形 | `high_tight_flag_screener.py` |
| 金凤凰 | `jin_feng_huang_screener.py` |
| 试盘线 | `shi_pan_xian_screener.py` |
| 双手板 | `shuang_shou_ban_screener.py` |
| 银凤凰 | `yin_feng_huang_screener.py` |
| 涨停倍量阴 | `zhang_ting_bei_liang_yin_screener.py` |

---

## 根本原因分析

### 1. `current_date` 属性没有交易日检查

**位置**：`screeners/base_screener.py` Line 499-518

```python
@property
def current_date(self) -> str:
    """返回 YYYY-MM-DD 字符串"""
    if self._current_date is None:
        dt = self.get_latest_data_date() or date.today()  # ❌ 没有检查是否是交易日
        self._current_date = dt
    if isinstance(self._current_date, date):
        return self._current_date.strftime("%Y-%m-%d")
    return str(self._current_date)[:10]
```

**问题**：
- `get_latest_data_date()` 返回的是 DB 中的最新日期，这个日期一定是交易日
- 但如果用户直接设置 `self.current_date = '2026-04-06'`（非交易日），setter 没有验证

### 2. `get_stock_data()` 直接使用 `current_date` 作为查询条件

**位置**：`screeners/base_screener.py` Line 521-554

```python
def get_stock_data(self, code: str, days: int = 120) -> Optional["pd.DataFrame"]:
    sql = """
        SELECT dp.trade_date, dp.open, dp.high, dp.low, dp.close,
               dp.volume, COALESCE(dp.amount, 0) AS amount,
               COALESCE(dp.turnover, 0) AS turnover,
               COALESCE(dp.pct_change, 0) AS pct_change
        FROM daily_prices dp
        WHERE dp.code = ?
          AND dp.trade_date <= ?    # ❌ 直接使用 current_date，没有交易日验证
        ORDER BY dp.trade_date DESC
        LIMIT ?
    """
    df = pd.read_sql_query(
        sql, conn,
        params=(code, self.current_date, days),  # ❌
    )
```

**问题**：如果 `current_date` 是非交易日，SQL 会查询到错误的数据范围

### 3. `check_data_availability()` 检查不完整

**位置**：`screeners/base_screener.py` Line 556-568

```python
def check_data_availability(self, check_date: str) -> bool:
    """检查数据库中是否存在 check_date 当天或之前的数据。"""
    try:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT MAX(trade_date) FROM daily_prices"
            ).fetchone()
        if not row or not row[0]:
            return False
        return str(row[0])[:10] >= check_date[:10]  # ❌ 只检查日期大小，不检查是否是交易日
    except Exception as exc:
        logger.warning("check_data_availability 失败: %s", exc)
        return False
```

**问题**：这个方法只检查 DB 最新日期是否 >= 指定日期，但：
- 不检查指定日期是否是交易日
- 不检查指定日期到 DB 最新日期之间是否都是非交易日

---

## 现有交易日历功能

系统已有完整的交易日历模块：`scripts/trading_calendar.py`

**可用接口：**
```python
from scripts.trading_calendar import (
    is_trading_day,              # 检查某天是否是交易日
    get_recent_trading_day,        # 获取最近的交易日
    get_trading_days_between,      # 获取日期区间内的所有交易日
    get_latest_db_trade_date,      # 从 DB 获取最新交易日
)
```

**测试结果：**
```python
# 测试结果
from datetime import date
today = date(2026, 4, 7)        # 4月7日（周一）
yesterday = date(2026, 4, 6)    # 4月6日（周日）

is_trading_day(today)       # True  ✅
is_trading_day(yesterday)   # False ❌
get_recent_trading_day(yesterday)  # 返回 2026-04-03（最近的交易日）
```

**结论**：交易日历功能正常，但筛选器没有使用它。

---

## 修复方案

### 方案A：在 BaseScreener 中自动修正（推荐）

**修改位置**：`screeners/base_screener.py`

#### 修改1：`current_date` setter 自动调整为交易日

```python
# Line 508-518 修改为：
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

    # ✅ 新增：如果不是交易日，自动调整为最近的交易日
    from trading_calendar import get_recent_trading_day
    if not is_trading_day(dt):
        logger.warning(
            "[%s] %s 不是交易日，自动调整为 %s",
            self.screener_name, dt, get_recent_trading_day(dt)
        )
        dt = get_recent_trading_day(dt)

    self._current_date = dt
```

#### 修改2：`check_data_availability()` 增加交易日检查

```python
# Line 556-568 修改为：
def check_data_availability(self, check_date: str) -> bool:
    """检查数据库中是否存在 check_date 当天或之前的数据，并且 check_date 是交易日。"""
    # ✅ 新增：检查是否是交易日
    from trading_calendar import is_trading_day
    try:
        check_dt = datetime.strptime(check_date[:10], "%Y-%m-%d").date()
        if not is_trading_day(check_dt):
            logger.warning(
                "[%s] %s 不是交易日，无法进行筛选",
                self.screener_name, check_dt
            )
            return False
    except ValueError:
        return False

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
```

#### 修改3：在 `run_screening()` 开始时显式验证（可选）

```python
# 在 run_screening() 方法开始处添加：
def run_screening(self, date_str: Optional[str] = None, ...):
    if date_str:
        self.current_date = date_str

    # ✅ 新增：显式验证当前日期是否是交易日
    from trading_calendar import is_trading_day
    current_dt = datetime.strptime(self.current_date, "%Y-%m-%d").date()
    if not is_trading_day(current_dt):
        logger.warning(
            "[%s] 当前日期 %s 不是交易日，筛选器不运行",
            self.screener_name, current_dt
        )
        return []
```

---

### 方案B：在每个筛选器中手动添加（不推荐）

在每个筛选器的 `run_screening()` 方法开始处添加交易日检查。

**缺点**：需要修改15个文件，容易遗漏，维护困难。

---

## 影响评估

### 修复前的影响
| 场景 | 影响 |
|------|------|
| 用户指定非交易日日期 | ❌ 基于错误数据筛选，结果不准确 |
| 数据同步后立即运行 | ⚠️ 可能使用周末日期，但影响较小（因为无数据） |
| 自动任务运行 | ⚠️ 如果调度在非交易日触发，会出问题 |

### 修复后的影响
| 场景 | 影响 |
|------|------|
| 用户指定非交易日日期 | ✅ 自动调整为最近的交易日，或直接拒绝 |
| 数据同步后立即运行 | ✅ 自动使用正确的交易日 |
| 自动任务运行 | ✅ 始终在交易日运行 |

---

## 测试建议

修复后，测试以下场景：

### 测试1：指定非交易日
```bash
# 指定周末日期
python3 screeners/er_ban_hui_tiao_screener.py --date 2026-04-06

# 预期：自动调整为 2026-04-03 或 2026-04-07（取决于修复逻辑）
# 或直接返回空列表并提示非交易日
```

### 测试2：指定节假日
```bash
# 指定春节假期
python3 screeners/er_ban_hui_tiao_screener.py --date 2026-02-09

# 预期：自动调整为假期前最后一个交易日
```

### 测试3：正常交易日
```bash
# 指定周一（正常交易日）
python3 screeners/er_ban_hui_tiao_screener.py --date 2026-04-07

# 预期：正常运行，基于 2026-04-07 的数据
```

### 测试4：不指定日期
```bash
# 使用默认日期（当前 DB 最新交易日）
python3 screeners/er_ban_hui_tiao_screener.py

# 预期：使用 DB 最新交易日（2026-04-07），正常运行
```

---

## 优先级

| 优先级 | 修改项 | 风险 |
|--------|--------|------|
| 🔴 高 | `current_date` setter 自动修正 | 低 |
| 🟡 中 | `check_data_availability()` 增加检查 | 低 |
| 🟢 低 | `run_screening()` 显式验证 | 极低 |

---

## 总结

**问题**：所有15个筛选器都没有交易日检查，可能在使用非交易日日期时产生错误结果。

**原因**：`base_screener.py` 中的 `current_date` setter 和 `get_stock_data()` 方法没有交易日验证逻辑。

**解决方案**：在 `BaseScreener` 的 `current_date` setter 中自动调整为交易日，这是最简单且影响最小的方案。

**建议**：
1. 采用方案A（在 BaseScreener 中自动修正）
2. 优先修复 `current_date` setter（高优先级）
3. 补充 `check_data_availability()` 检查（中优先级）
4. 运行测试验证修复效果

---

## 生成日期

2026-04-07
