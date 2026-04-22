# 开发指南

## 概述

本文档指导开发者如何参与 STOCKPREDICTION 项目的开发，包括环境配置、代码规范和贡献流程。

## 开发环境

### 系统要求

- **操作系统**: macOS, Linux, Windows (推荐 macOS/Linux)
- **Python**: 3.10+
- **内存**: 8GB+ (推荐 16GB)
- **磁盘**: 10GB+ 可用空间

### 环境配置

#### 1. 克隆项目

```bash
cd /Users/mac/NeoTrade2/STOCKPREDICTION
```

#### 2. 创建虚拟环境

```bash
# 使用 venv
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

# 使用 conda (推荐)
conda create -n stockprediction python=3.10
conda activate stockprediction
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 4. 安装 TA-Lib (可选但推荐)

```bash
# macOS
brew install ta-lib

# Linux
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install

# 安装 Python 绑定
pip install TA-Lib
```

如果 TA-Lib 安装困难，可以使用替代方案：

```bash
pip install pandas-ta
```

#### 5. 验证安装

```bash
python -c "import pandas; import xgboost; import ta; print('All dependencies OK')"
```

### IDE 配置

#### VS Code

推荐安装以下扩展：

- Python
- Pylance
- Black Formatter
- isort

配置 `.vscode/settings.json`:

```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.sortImports.args": "--profile black",
    "editor.formatOnSave": true,
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

#### PyCharm

1. 打开项目
2. Settings → Project → Python Interpreter → 选择虚拟环境
3. Settings → Tools → External Tools → 添加 Black 和 isort

## 代码规范

### Python 风格

遵循 PEP 8 规范，使用以下工具自动格式化：

```bash
# 格式化代码
black scripts/ models/

# 排序 import
isort scripts/ models/

# 代码检查
pylint scripts/ models/
# 或
flake8 scripts/ models/
```

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `StockPredictor`, `LabelGenerator` |
| 函数名 | snake_case | `compute_features`, `get_all_stocks` |
| 变量名 | snake_case | `max_gain`, `trade_date` |
| 常量 | UPPER_SNAKE_CASE | `TARGET_HORIZON_MIN`, `DB_PATH` |
| 私有方法/变量 | _leading_underscore | `_init_target_db`, `_load_config` |

### 类型提示

所有公共函数和类方法应包含类型提示：

```python
from typing import List, Dict, Optional, Tuple
import pandas as pd

def get_stock_prices(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取股票价格数据"""
    ...

def calculate_max_gain(
    prices: pd.Series,
    min_days: int = 21,
    max_days: int = 34
) -> Tuple[float, int, Optional[int]]:
    """计算最大涨幅"""
    ...
```

### 文档字符串

使用 Google 风格的文档字符串：

```python
def generate_labels_for_stock(
    self,
    code: str,
    name: str,
    start_date: str,
    end_date: str
) -> List[Dict]:
    """为单只股票生成标签。

    Args:
        code: 股票代码 (如 '000001.SZ')
        name: 股票名称
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)

    Returns:
        标签列表，每个标签包含 code, name, base_date, label 等字段

    Raises:
        ValueError: 当日期格式不正确时

    Example:
        >>> generator = LabelGenerator()
        >>> labels = generator.generate_labels_for_stock(
        ...     '000001.SZ', '平安银行', '2024-09-01', '2026-03-31'
        ... )
        >>> len(labels)
        150
    """
    ...
```

## 项目结构

### 目录组织

```
STOCKPREDICTION/
├── docs/                   # 文档
│   ├── INDEX.md
│   ├── DATA_MODEL.md
│   ├── FEATURE_ENGINEERING.md
│   └── ...
├── data/                   # 数据目录（不提交到 git）
│   ├── labels.db
│   ├── features.db
│   └── ...
├── models/                 # 模型代码
│   ├── database.py
│   ├── feature_engine.py
│   └── predictor.py
├── scripts/                # 脚本
│   ├── config.py
│   ├── backtest_labels.py
│   ├── compute_features.py
│   └── ...
├── notebooks/              # Jupyter 笔记本
├── dashboard/              # Dashboard 代码
├── logs/                   # 日志目录（不提交）
├── reports/                # 报告目录（不提交）
├── CLAUDE.md              # Claude Code 指南
├── requirements.txt       # 依赖
├── README.md              # 项目说明
└── RESEARCH_PLAN.md       # 研究计划
```

### 文件命名

- 脚本文件: `verb_noun.py` (如 `compute_features.py`)
- 模块文件: `noun.py` (如 `database.py`)
- 笔记本: `description.ipynb` (如 `exploratory_analysis.ipynb`)

## 开发流程

### 功能开发流程

1. **创建分支**
   ```bash
   git checkout -b feature/feature-name
   ```

2. **开发代码**
   - 遵循代码规范
   - 添加类型提示
   - 编写文档字符串

3. **测试**
   ```bash
   # 运行测试（如果有）
   pytest tests/

   # 手动测试
   python scripts/backtest_labels.py --start-date 2024-12-01 --end-date 2024-12-31
   ```

4. **代码审查**
   - 自我审查
   - 使用 pylint/flake8 检查

5. **提交代码**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

6. **合并到主分支**
   ```bash
   git checkout main
   git merge feature/feature-name
   ```

### 提交信息规范

使用 Conventional Commits 格式：

```
<type>: <description>

[optional body]

[optional footer]
```

类型 (type):
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建过程或辅助工具变动

示例：
```
feat: add SHAP value calculation for model interpretation

- Add shap dependency to requirements.txt
- Implement SHAP explainer in model.py
- Add visualization functions in utils.py

Closes #123
```

## 调试技巧

### 日志配置

使用 logging 模块进行日志记录：

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Starting processing...")
logger.debug(f"Processing {len(data)} records")
logger.error(f"Failed to process {code}: {e}")
```

### 断点调试

```python
# 在代码中插入断点
import pdb; pdb.set_trace()

# 或使用 ipdb
import ipdb; ipdb.set_trace()
```

### 性能分析

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# 执行代码
result = your_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(20)
```

## 测试

### 单元测试

```python
# tests/test_database.py
import pytest
from models.database import init_db, get_engine

def test_database_init():
    """测试数据库初始化"""
    db_path = Path("test.db")
    engine = init_db(db_path)
    assert engine is not None
    # 清理
    db_path.unlink()

def test_connection():
    """测试数据库连接"""
    from scripts.config import NEOTRADE_DB_PATH
    conn = sqlite3.connect(str(NEOTRADE_DB_PATH), timeout=30)
    result = conn.execute("SELECT 1").fetchone()
    assert result[0] == 1
```

运行测试：
```bash
pytest tests/
pytest tests/ -v  # 详细输出
pytest tests/ --cov=scripts  # 覆盖率
```

## 性能优化

### 数据库查询优化

```python
# ❌ 低效：多次查询
for code in codes:
    df = pd.read_sql(f"SELECT * FROM daily_prices WHERE code = '{code}'", conn)

# ✅ 高效：一次查询
df = pd.read_sql("SELECT * FROM daily_prices WHERE code IN (?,?,?)", conn, params=codes)
```

### 向量化操作

```python
# ❌ 低效：循环
for i in range(len(df)):
    df['ma5'][i] = df['close'][i-4:i+1].mean()

# ✅ 高效：向量化
df['ma5'] = df['close'].rolling(5).mean()
```

## 常见问题

### Q: TA-Lib 安装失败

A: 使用替代方案：
```bash
pip install pandas-ta
```

### Q: 内存不足

A: 使用分批处理：
```python
# 分批加载和处理数据
batch_size = 100
for i in range(0, len(stocks), batch_size):
    batch = stocks[i:i+batch_size]
    process_batch(batch)
```

### Q: 数据库锁定

A: 使用只读连接或增加超时：
```python
conn = sqlite3.connect(db_path, timeout=60)
```

## 贡献指南

### 报告问题

使用 GitHub Issues 报告问题，包含：
- 问题描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息

### 提交代码

1. Fork 项目
2. 创建功能分支
3. 编写代码和测试
4. 提交 Pull Request
5. 等待代码审查

### 文档贡献

欢迎改进文档：
- 修正错误
- 添加示例
- 翻译文档
- 改进说明

## 许可证

本项目为研究项目，仅供个人使用。
