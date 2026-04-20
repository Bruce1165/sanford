# 杯柄测试筛选器对比分析

## 筛选器对比

| 项目 | coffee_cup_screener.py | cup_handle_test_screener.py |
|------|------------------------|---------------------------|
| 筛选器名称 | 咖啡杯形态筛选器 | 杯柄测试筛选器 |
| 基础文档 | 欧奈尔CANSLIM标准 | 欧奈尔咖啡杯选股测试版 |
| 主要目标 | 识别完整的杯柄形态 | 分两阶段：潜在标的→完成杯柄 |

---

## 参数配置对比

### 市值范围

| 参数 | coffee_cup | cup_handle_test |
|------|-----------|----------------|
| 最小流通市值 | 30亿 | **50亿** ✅ |
| 最大流通市值 | 1500亿 | **800亿** ✅ |

**差异**：cup_handle_test 严格限制在50-800亿，符合测试版文档要求

### 杯深参数

| 参数 | coffee_cup | cup_handle_test |
|------|-----------|----------------|
| 杯深最小 | 20% | **12%-15%** ✅ |
| 杯深最大 | 50% | **15%（绝对上限33%）** ✅ |

**差异**：cup_handle_test 更严格，要求杯深在12%-15%之间

### 柄部参数

| 参数 | coffee_cup | cup_handle_test |
|------|-----------|----------------|
| 柄部回撤 | 5%-12% | **≤杯深的50%** ✅ |
| 柄部均线 | 无 | **10日均线之上** ✅ |

**差异**：cup_handle_test 明确要求柄部最低价不低于杯底，且回撤不超过杯深一半

### 成交量条件

| 参数 | coffee_cup | cup_handle_test |
|------|-----------|----------------|
| 柄部缩量 | <85%前期均量 | **降至平均值以下** ✅ |
| 突破放量 | ≥2倍均量 | **≥6倍**（杯深70%处或突破时） ✅ |

**差异**：cup_handle_test 要求更明确的放量标准（6倍）

---

## 筛选逻辑对比

### coffee_cup_screener.py

**逻辑**：
1. 在数据中寻找完整的杯柄形态
2. 一次性输出所有符合条件的股票
3. 条件较为宽松（市值范围大、杯深范围大）

**特点**：
- 单阶段筛选
- 参数固定
- 输出单一结果

### cup_handle_test_screener.py

**逻辑**：三阶段筛选

**阶段1：潜在咖啡杯标的**
- 条件1：杯部右侧放量大（价格到杯深70%位置，当日+2日成交额≥6倍杯沿前10日均量）
- 条件2：突破放量大（首次突破杯沿，当日+2日成交额≥6倍杯沿前10日均量，或3日内满足）

**阶段2：咖啡杯标的**
- 条件3：形成杯柄（完成右侧形态后回调，形成杯柄）
  - 柄部回撤≤杯深的50%
  - 柄部最低价不低于杯底
  - 当前价格突破柄部（接近柄部高点）

**特点**：
- 两阶段输出（潜在+完成）
- 参数可配置
- 严格符合测试版文档

---

## 输出文件对比

### coffee_cup_screener.py

**文件**：
```
data/screeners/coffee_cup/{date}.xlsx
```

**字段**：
- 代码、名称、行业
- 杯沿日期/价格、杯底日期/价格
- 柄部信息
- 成交量信息
- 技术指标（均线、RS等）

### cup_handle_test_screener.py

**文件1**：
```
data/screeners/cup_handle_test/潜在咖啡杯标的_{date}.xlsx
```

**字段**：
- 代码、名称、总市值、流通市值、行业
- 选股日期、涨幅、成交额（万元）、换手率%
- 左侧阶段性最高价日期、左侧阶段性最高价
- 咖啡杯深度（%）、右侧自杯底涨幅（%）
- 咖啡杯形态持续时间（交易日数）
- 右侧成交放量幅度

**文件2**：
```
data/screeners/cup_handle_test/咖啡杯标的_{date}.xlsx
```

**字段**：
- 代码、名称、总市值、流通市值、行业
- 选股日期、涨幅、成交额（万元）、换手率%
- 左侧阶段性最高价日期、左侧阶段性最高价
- 咖啡杯深度（%）、右侧自杯底涨幅（%）
- 咖啡杯形态持续时间（交易日数）
- 右侧成交放量幅度（突破日+2日 / 杯沿前10日均量）
- **杯柄幅度**（自杯柄右侧阶段性高价的调整幅度）
- **杯柄持续时间**（自杯柄右侧阶段性最高价日至选股日的交易日数量）

---

## 关键差异总结

### 1. 筛选目标

| 筛选器 | 目标 |
|--------|------|
| coffee_cup | 识别完整的杯柄形态（欧奈尔标准）|
| cup_handle_test | 按测试版文档分阶段识别（潜在→完成）|

### 2. 市值过滤

| 筛选器 | 市值范围 |
|--------|----------|
| coffee_cup | 30-1500亿（较宽）|
| cup_handle_test | **50-800亿**（更精确，符合文档）|

### 3. 杯深要求

| 筛选器 | 杯深要求 |
|--------|----------|
| coffee_cup | 20%-50%（较宽松）|
| cup_handle_test | **12%-15%**（严格，符合文档）|

### 4. 成交量条件

| 筛选器 | 条件 |
|--------|------|
| coffee_cup | 柄部缩量<85%，突破放量≥2倍 |
| cup_handle_test | **杯深70%处放量≥6倍或突破放量≥6倍**（更明确）|

### 5. 输出策略

| 筛选器 | 输出 |
|--------|------|
| coffee_cup | 单一Excel，包含所有信息 |
| cup_handle_test | **两个Excel**（潜在+完成），分阶段监控 |

---

## 参数配置能力

### coffee_cup_screener.py

```python
# 参数硬编码在 OneilParams 类中
class OneilParams:
    CUP_PERIOD_MIN = 60
    CUP_PERIOD_MAX = 250
    # ... 其他参数都是硬编码
```

**配置方式**：
- 需要修改代码
- 通过命令行传递 params 参数

### cup_handle_test_screener.py

```python
# 参数类 + get_parameter_schema() 方法
class CupHandleTestParams:
    MARKET_CAP_MIN = 50.0
    MARKET_CAP_MAX = 800.0
    # ... 默认值硬编码

@classmethod
def get_parameter_schema(cls) -> Dict:
    return {
        'MARKET_CAP_MIN': {
            'type': 'float',
            'default': 50.0,
            'min': 10.0,
            'max': 200.0,
            'step': 10.0,
            'display_name': '最小流通市值（亿元）',
            'group': '筛选范围'
        },
        # ... 所有参数都可通过Dashboard配置
    }
```

**配置方式**：
- ✅ 所有参数都有 schema 定义
- ✅ 可通过 Dashboard 动态配置
- ✅ 可通过配置文件持久化

---

## 适用场景建议

### 使用 coffee_cup_screener.py 当：
- 需要快速识别所有杯柄形态
- 市值范围要求较宽（30-1500亿）
- 杯深要求较宽松（20%-50%）
- 需要传统欧奈尔标准参数

### 使用 cup_handle_test_screener.py 当：
- 严格遵循《欧奈尔咖啡杯选股测试版》文档
- 需要分阶段监控（潜在标的→完成标的）
- 市值范围精确（50-800亿）
- 需要动态调整参数
- 需要更严格的杯深要求（12%-15%）

---

## 测试建议

### 测试1：参数配置测试

```bash
# 运行新筛选器（使用默认参数）
python3 screeners/cup_handle_test_screener.py --date 2026-04-07 --no-check

# 预期：
# - 生成两个Excel文件
# - 潜在咖啡杯标的_xxx.xlsx
# - 咖啡杯标的_xxx.xlsx
```

### 测试2：对比运行

```bash
# 同时运行两个筛选器（同一日期）
python3 screeners/coffee_cup_screener.py --date 2026-04-07 --no-check
python3 screeners/cup_handle_test_screener.py --date 2026-04-07 --no-check

# 对比：
# - 匹配的股票数量
# - 匹配的股票列表
# - 各字段的差异
```

### 测试3：参数调整测试

```bash
# 调整市值范围
# 在Dashboard中修改 MARKET_CAP_MIN 和 MARKET_CAP_MAX

# 调整杯深范围
# 在Dashboard中修改 CUP_DEPTH_MIN 和 CUP_DEPTH_MAX

# 重新运行筛选器，观察结果变化
```

---

## 生成日期

2026-04-07

---

## 相关文档

- [docs/er_ban_hui_tiao_comparison.md](er_ban_hui_tiao_comparison.md) - 二板回调筛选器对比
- [docs/trading_day_issue_analysis.md](trading_day_issue_analysis.md) - 交易日检查问题分析
- [docs/screener_fixes_plan.md](screener_fixes_plan.md) - 修复计划
- [docs/screener_fixes_summary.md](screener_fixes_summary.md) - 修复总结
