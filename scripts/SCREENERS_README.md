# 股票筛选器系统 - 使用说明

## 🚀 Development Best Practices (CRITICAL)

**BEFORE ANY SCREENER DEVELOPMENT, Claude Code MUST:**

### 📋 1. Development Planning
- **[ ] Make development plan before coding**
- **[ ] Design data structures and algorithms first**
- **[ ] Plan testing approach and validation criteria**
- **[ ] Consider edge cases and error handling
- **[ ] Review existing similar screeners for patterns

### 📝 2. Pseudocode Before Real Coding
- **[ ] Write pseudocode file before implementation**
- **[ ] Document algorithm logic and data flow
- **[ ] Define input/output specifications
- **[ ] Plan error handling and edge cases
- **[ ] Update pseudocode as design evolves

### 💻 3. Update Pseudocode Before Real Code
- **[ ] Update pseudocode file before modifying real code**
- **[ ] Ensure implementation matches pseudocode design
- **[ ] Document any deviations from pseudocode
- **[ ] Keep pseudocode as living documentation

### 🗂️ 4. File Backup and Safety
- **[ ] Backup current file before modifying**
- **[ ] Keep backup until all modifications verified
- **[ ] Delete backup only after complete verification**
- **[ ] Test backup restore if needed

### 🔡 5. Code Quality Standards
- **[ ] NO Chinese characters in real code files**
- **[ ] English variable names and comments only**
- **[ ] Follow existing code style and patterns**
- **[ ] Use descriptive variable and function names**
- **[ ] Add docstrings to new functions and classes**

### 🐛 6. Debugging and Problem Solving
- **[ ] Use debugging messages for tracing execution**
- **[ ] Add debug logging for cache/version issues**
- **[ ] Document critical points and decision logic
- **[ ] Use print statements for key algorithm steps**
- **[ ] STOP if stuck in circular problem solving - ask for help**

### 🧹 7. Log File Management
- **[ ] Clean up log files after each work chunk**
- **[ ] Remove temporary/debug logs after verification**
- **[ ] Archive old log files periodically
- **[ ] Keep logs structured and searchable

### 🎯 8. Real and Professional Approach
- **[ ] Keep it real - no fictional examples or placeholders**
- **[ ] Use actual data and realistic scenarios**
- **[ ] Base decisions on facts and requirements**
- **[ ] Document assumptions and constraints clearly
- **[ ] Focus on working solutions, not experimental code

### ✅ Pre-Work Checklist Summary
Before starting screener development, Claude Code must:
1. Read this development best practices section
2. Create comprehensive development plan
3. Write pseudocode for algorithm design
4. Plan testing and validation approach
5. Review existing similar screeners
6. Design data structures and outputs
7. Plan error handling and edge cases

---

## Directory Structure

```
data/screeners/
├── coffee_cup/              # 咖啡杯形态筛选器
│   ├── 2026-03-13.xlsx      # 筛选结果
│   └── charts/              # 图表目录
│       └── 2026-03-13/      # 按日期组织的图表
├── jin_feng_huang/          # 涨停金凤凰筛选器
├── yin_feng_huang/          # 涨停银凤凰筛选器
├── shi_pan_xian/            # 涨停试盘线筛选器
├── er_ban_hui_tiao/         # 二板回调筛选器
└── zhang_ting_bei_liang_yin/ # 涨停倍量阴筛选器
```

## 新模块说明

### 1. 交易日历模块 (`trading_calendar.py`)

自动处理交易日历，跳过周末和节假日。

```python
from trading_calendar import TradingCalendar, get_recent_trading_day

# 获取交易日历实例
calendar = TradingCalendar()

# 获取最近交易日
recent_day = calendar.get_recent_trading_day()  # "2026-03-13"

# 获取N个交易日前的日期
five_days_ago = calendar.get_n_trading_days_ago(5)

# 获取交易日窗口
trading_days = calendar.get_trading_days_window("2026-03-13", 10)
```

### 2. 新闻抓取模块 (`news_fetcher.py`)

从新浪财经抓取个股新闻，支持24小时缓存。

```python
from news_fetcher import NewsFetcher, get_news_summary

# 获取新闻
fetcher = NewsFetcher()
news = fetcher.get_news("600519", max_news=5)

# 获取新闻摘要
summary = fetcher.get_news_summary("600519")
```

### 3. LLM分析模块 (`llm_analyzer.py`)

使用LLM分析上涨原因、行业分类和相关概念。

```python
from llm_analyzer import LLMAnalyzer, analyze_stock

# 分析单只股票
analyzer = LLMAnalyzer()
result = analyzer.analyze_stock(
    stock_code="600519",
    stock_name="贵州茅台",
    news_summary="...",
    price_data={'close': 1800, 'pct_change': 2.5}
)

# 返回结果包含：
# - 上涨原因
# - 行业分类
# - 相关概念
# - 新闻摘要
# - 分析置信度
```

### 4. 进度跟踪模块 (`progress_tracker.py`)

支持断点续传，中断后能从上次位置继续。

```python
from progress_tracker import ProgressTracker

tracker = ProgressTracker('coffee_cup')

# 开始任务
tracker.start(total_stocks=4663)

# 更新进度
tracker.update(processed=100, matched=5, current_code='600519')

# 检查是否可以恢复
if tracker.is_resumable():
    resume_point = tracker.get_resume_point()

# 完成任务
tracker.complete(success=True)
```

### 5. 输出管理模块 (`output_manager.py`)

统一管理Excel输出和图表目录。

```python
from output_manager import OutputManager

manager = OutputManager('coffee_cup')

# 保存结果
manager.save_results(results)

# 保存带分析的结果
manager.save_with_analysis(results, analysis_data)

# 获取图表目录
charts_dir = manager.get_charts_dir("2026-03-13")
```

## 筛选器使用

### 单独运行筛选器

```bash
# 咖啡杯形态筛选器
python3 scripts/coffee_cup_screener.py --date 2026-03-13

# 涨停金凤凰筛选器
python3 scripts/jin_feng_huang_screener.py --date 2026-03-13

# 涨停银凤凰筛选器
python3 scripts/yin_feng_huang_screener.py --date 2026-03-13

# 涨停试盘线筛选器
python3 scripts/shi_pan_xian_screener.py --date 2026-03-13

# 二板回调筛选器
python3 scripts/er_ban_hui_tiao_screener.py --date 2026-03-13

# 涨停倍量阴筛选器
python3 scripts/zhang_ting_bei_liang_yin_screener.py --date 2026-03-13
```

### 运行所有筛选器

```bash
# 运行所有筛选器
python3 scripts/run_all_screeners.py --date 2026-03-13

# 运行指定筛选器
python3 scripts/run_all_screeners.py --date 2026-03-13 --screeners coffee_cup er_ban_hui_tiao

# 禁用新闻和LLM分析（快速模式）
python3 scripts/run_all_screeners.py --date 2026-03-13 --no-news --no-llm

# 强制重新开始（忽略断点续传）
python3 scripts/run_all_screeners.py --date 2026-03-13 --restart
```

### 生成图表

```bash
# 为筛选结果生成图表
python3 scripts/plot_coffee_cup_charts.py --date 2026-03-13

# 生成组合图表（多只股票一页）
python3 scripts/plot_coffee_cup_charts.py --date 2026-03-13 --combined

# 限制生成数量
python3 scripts/plot_coffee_cup_charts.py --date 2026-03-13 --max-charts 20
```

## 命令行参数

### 通用参数（所有筛选器）

- `--date`: 目标日期 (YYYY-MM-DD)
- `--no-news`: 禁用新闻抓取
- `--no-llm`: 禁用LLM分析
- `--no-progress`: 禁用进度跟踪
- `--restart`: 强制重新开始
- `--db-path`: 数据库路径 (默认: data/stock_data.db)

### 筛选器特定参数

#### 咖啡杯筛选器
无额外参数

#### 涨停金凤凰筛选器
- `--min-days`: 最小横盘天数 (默认: 3)
- `--max-days`: 最大横盘天数 (默认: 5)
- `--max-pullback`: 最大回调幅度 (默认: 0.0)
- `--no-gap`: 不要求保留缺口
- `--shrink-threshold`: 缩量阈值 (默认: 0.5)
- `--breakout-ratio`: 突破时放量倍数 (默认: 1.5)

#### 涨停银凤凰筛选器
- `--min-days`: 最小回调天数 (默认: 2)
- `--max-days`: 最大回调天数 (默认: 7)
- `--max-callback`: 最大回调幅度 (默认: 0.50)
- `--shrink-threshold`: 缩量阈值 (默认: 0.6)
- `--breakout-ratio`: 突破时放量倍数 (默认: 1.3)

#### 涨停试盘线筛选器
- `--consolidation-days`: 低位横盘判断天数 (默认: 20)
- `--high-volume-lookback`: 高量阳线回看周期 (默认: 30)
- `--max-consolidation-gain`: 横盘期最大涨幅 (默认: 0.10)
- `--shrink-threshold`: 缩量阈值 (默认: 0.25)
- `--callback-max-days`: 最大回调天数 (默认: 10)
- `--breakout-ratio`: 再次放量倍数 (默认: 1.5)

#### 二板回调筛选器
- `--limit-days`: 时间范围（交易日） (默认: 21)

#### 涨停倍量阴筛选器
- `--limit-days`: 时间范围（交易日） (默认: 21)

## 输出字段

### 基础字段
- 股票代码
- 股票名称
- 当前价格
- 当前涨幅%
- 换手率%

### LLM分析字段
- 上涨原因
- 行业分类
- 相关概念
- 新闻摘要
- 分析置信度

### 筛选器特定字段

#### 咖啡杯形态
- 收盘价
- 放量倍数
- 成交额(万)
- 杯柄日期
- 杯柄价格
- 杯沿价格
- 价格差%
- 间隔天数
- 杯深%

#### 涨停金凤凰
- 涨停日期
- 涨停收盘价
- 涨停最高价
- 缺口上沿
- 缺口下沿
- 横盘天数
- 横盘高点
- 横盘低点
- 是否缩倍量
- 突破日期
- 距涨停天数

#### 涨停银凤凰
- 涨停日期
- 涨停收盘价
- 支撑位价格
- 回调天数
- 回调低点
- 回调高点
- 是否缩量
- 最大回调%
- 突破日期
- 突破价格
- 突破放量倍数

#### 涨停试盘线
- 高量日期
- 高量收盘价
- 高量成交量
- 涨停日期
- 涨停收盘价
- 涨停最高价
- 涨停最低价
- 涨停成交量
- 回调天数
- 是否缩量
- 回调期最小量
- 缩量比例
- 突破日期

#### 二板回调
- 二板日期
- 距今天数
- 首板最低价
- 二板最高价
- 支撑位距离%
- 回调状态

#### 涨停倍量阴
- 涨停日期
- 倍量阴日期
- 地量日期
- 涨停收盘价
- 倍量阴开盘价
- 倍量阴收盘价
- 倍量阴成交量
- 涨停成交量
- 倍量比例
- 地量成交量
- 地量比例
- 支撑位
- 支撑位距离%

## 测试

```bash
# 运行所有测试
python3 scripts/test_screeners.py
```

## 注意事项

1. **LLM分析**: 需要配置OpenAI API密钥环境变量 `OPENAI_API_KEY`
2. **新闻抓取**: 依赖网络连接，建议启用缓存避免重复请求
3. **进度跟踪**: 进度文件保存在 `data/progress/` 目录
4. **缓存**: 新闻和LLM分析结果缓存24小时
5. **向后兼容**: 旧筛选器仍然可以单独运行
