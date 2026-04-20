# 历史筛选报告处理方案

## 当前情况

发现历史筛选报告文件共 **19个Excel文件**，分布如下：

| 日期 | 文件数 | 说明 |
|------|--------|------|
| 03-13 | 2 | breakout_20day, breakout_main |
| 03-16 | 1 | breakout_20day |
| 03-17 | 2 | intraday盘中筛选 |
| 03-18 | 12 | 大部分筛选器 |
| 03-19 | 2 | intraday盘中筛选, shi_pan_xian |

## 处理方案

### 方案A: 重新生成所有报告（推荐）

**操作**: 删除旧文件，重新运行所有筛选器生成新报告

**优点**:
- 所有报告格式统一
- 无兼容性问题
- 数据最新

**缺点**:
- 历史数据需要重新计算
- 耗时约10-15分钟

**执行命令**:
```bash
# 备份旧文件
mv data/screeners data/screeners_backup_$(date +%Y%m%d)

# 重新运行所有筛选器
python3 scripts/coffee_cup_screener.py --date 2026-03-18
python3 scripts/jin_feng_huang_screener.py --date 2026-03-18
... (其他筛选器)
```

---

### 方案B: 保留最新，仅修复问题文件

**操作**: 只保留03-18和03-19的报告，早期文件归档

**优点**:
- 快速处理
- 保留近期重要数据
- 节省空间

**执行**:
```bash
# 归档03-13, 03-16的旧报告
mkdir -p data/screeners_archive
cp data/screeners/breakout_20day/2026-03-13.xlsx data/screeners_archive/
cp data/screeners/breakout_main/2026-03-13.xlsx data/screeners_archive/

# 删除旧文件
rm data/screeners/breakout_20day/2026-03-13.xlsx
rm data/screeners/breakout_main/2026-03-13.xlsx
```

---

### 方案C: 批量转换为CSV格式

**操作**: 将所有Excel转换为CSV，确保兼容性

**优点**:
- CSV格式最稳定
- 所有Excel都能打开
- 保留所有历史数据

**执行**:
```python
import pandas as pd
from pathlib import Path

for xlsx_file in Path('data/screeners').glob('**/*.xlsx'):
    df = pd.read_excel(xlsx_file)
    csv_file = xlsx_file.with_suffix('.csv')
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
```

---

## 建议

**推荐方案A**: 
- 当前筛选器已全部修复
- 重新生成可确保格式统一
- 同时生成CSV备份

**实施步骤**:
1. 备份现有报告
2. 批量重新运行筛选器
3. 生成CSV备用格式
4. 验证文件可正常打开

---

请确认采用哪种方案？
