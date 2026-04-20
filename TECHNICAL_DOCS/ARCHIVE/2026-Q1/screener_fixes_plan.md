# 筛选器修复计划

## 问题汇总

### 问题1：二板回调筛选器规则不匹配

**文件**：`screeners/er_ban_hui_tiao_screener.py`

**差异详情**：参见 [docs/er_ban_hui_tiao_comparison.md](er_ban_hui_tiao_comparison.md)

| 项目 | 用户规则 | 现有代码 | 状态 |
|------|----------|----------|------|
| 时间范围 | 34天 | 14天 | ❌ |
| 信号一 | 2个条件 | 3个条件（多1个） | ❌ |
| 信号二 | 1个条件 | 1个条件+容忍度 | ⚠️ |
| 信号三 | 2个条件 | 4个条件（多2个） | ❌ |

### 问题2：所有筛选器缺失交易日检查（影响所有15个筛选器）

**文件**：`screeners/base_screener.py`

**核心问题**：
- `current_date` setter 没有交易日验证
- SQL 查询使用 `WHERE trade_date <= current_date` 直接用传入的日期
- 如果 `current_date` 是非交易日，会获取过期数据

**影响场景**：
```bash
# 用户指定昨天（周日）
python3 screeners/er_ban_hui_tiao_screener.py --date 2026-04-06

# 实际发生：
# SQL: WHERE trade_date <= '2026-04-06'
# DB最新是2026-04-07（周一），但因为 > '2026-04-06'，不会被查询到
# 返回数据截止到2026-04-03
# 筛选器基于过期数据运行 ❌
```

---

## 修复计划

### 优先级1：修复交易日检查（基础性，影响所有筛选器）

**文件**：`screeners/base_screener.py`

#### 修复1.1：`current_date` setter 自动调整为交易日

**位置**：Line 508-518

**修改内容**：
```python
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
    try:
        from scripts.trading_calendar import is_trading_day, get_recent_trading_day
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
```

#### 修复1.2：`check_data_availability()` 增加交易日检查（可选）

**位置**：Line 556-568

**修改内容**：
```python
def check_data_availability(self, check_date: str) -> bool:
    """检查数据库中是否存在 check_date 当天或之前的数据，并且 check_date 是交易日。"""
    # ✅ 新增：检查是否是交易日
    try:
        from scripts.trading_calendar import is_trading_day
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
```

---

### 优先级2：修复二板回调筛选器规则

**文件**：`screeners/er_ban_hui_tiao_screener.py`

#### 修复2.1：修改时间范围

**位置**：Line 42

**修改**：
```python
# 修改前
LIMIT_DAYS = 14  # 最近14个交易日

# 修改后
LIMIT_DAYS = 34  # 最近34个交易日
```

#### 修复2.2：移除信号一的额外条件

**位置**：Line 154-157

**修改**：删除以下代码
```python
# 删除这段
# 检查第2个涨停日成交额 < 第1个涨停日成交额
second_amount = df.iloc[i + 1]['amount']
if second_amount >= first_amount:
    continue
```

#### 修复2.3：修改信号二容忍度

**位置**：Line 52

**修改**：
```python
# 修改前
pullback_tolerance: float = 0.99,

# 修改后
pullback_tolerance: float = 1.0,
```

#### 修复2.4：移除信号三的额外条件

**位置**：Line 218-220

**修改**：删除阳线检查
```python
# 删除这段
# 2. 阳线（收盘价 > 开盘价）
if current['close'] <= current['open']:
    return False
```

**位置**：Line 222-230

**修改**：删除成交额最大检查
```python
# 删除这段
# 3. 成交额为T日（首板）以来的最大成交额
# 获取从首板到当前日的所有成交额
period_amounts = df.iloc[first_idx:idx + 1]['amount']
if period_amounts.empty:
    return False
max_amount = period_amounts.max()

if current['amount'] < max_amount:
    return False
```

---

## 测试计划

### 测试1：交易日检查修复

```bash
# 测试1.1：指定非交易日（应该自动调整）
python3 screeners/er_ban_hui_tiao_screener.py --date 2026-04-06

# 预期：日志显示 "2026-04-06 不是交易日，自动调整为 2026-04-03"

# 测试1.2：指定正常交易日
python3 screeners/er_ban_hui_tiao_screener.py --date 2026-04-07

# 预期：正常运行

# 测试1.3：不指定日期（使用DB最新）
python3 screeners/er_ban_hui_tiao_screener.py

# 预期：使用 DB 最新交易日（2026-04-07），正常运行
```

### 测试2：二板回调筛选器规则修复

```bash
# 测试2.1：对比修复前后的结果数量
# 修复前
python3 screeners/er_ban_hui_tiao_screener.py --date 2026-04-07 --no-check
# 保存结果为 before_fix.xlsx

# 修复后
python3 screeners/er_ban_hui_tiao_screener.py --date 2026-04-07 --no-check
# 保存结果为 after_fix.xlsx

# 对比两个文件的结果数量和股票列表
```

---

## 风险评估

| 修复项 | 风险级别 | 说明 |
|--------|-----------|------|
| `current_date` setter 交易日检查 | 🟢 低 | 自动调整为交易日，不会破坏现有逻辑 |
| `check_data_availability()` 交易日检查 | 🟢 低 | 增加防御性检查，提高健壮性 |
| 二板回调时间范围 14→34天 | 🟡 中 | 可能增加匹配数量，但符合用户要求 |
| 二板回调移除额外条件 | 🟡 中 | 可能增加匹配数量，符合用户规则 |

---

## 回滚计划

如果修复后出现问题：

```bash
# 回滚方法：使用 git
git checkout screeners/base_screener.py
git checkout screeners/er_ban_hui_tiao_screener.py

# 或者手动备份修改前的文件
cp screeners/base_screener.py screeners/base_screener.py.bak
cp screeners/er_ban_hui_tiao_screener.py screeners/er_ban_hui_tiao_screener.py.bak
```

---

## 实施步骤

- [x] 问题分析和文档生成
- [x] 修复计划制定
- [ ] 修复 `base_screener.py` 的交易日检查
- [ ] 修复 `er_ban_hui_tiao_screener.py` 的规则匹配
- [ ] 运行测试验证修复效果
- [ ] 对比修复前后的结果
- [ ] 更新文档和注释

---

## 生成日期

2026-04-07
