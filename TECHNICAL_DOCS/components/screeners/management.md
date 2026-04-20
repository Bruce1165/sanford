# 筛选器管理指南

**版本**: v1.0  
**创建日期**: 2026-04-13  
**适用范围**: NeoTrade2 筛选器系统

---

## 📋 目录

1. [筛选器架构概览](#筛选器架构概览)
2. [添加新筛选器](#添加新筛选器)
3. [修改现有筛选器](#修改现有筛选器)
4. [删除筛选器](#删除筛选器)
5. [服务重启指南](#服务重启指南)
6. [文档更新流程](#文档更新流程)
7. [常见问题](#常见问题)

---

## 筛选器架构概览

### 目录结构

```
NeoTrade2/
├── screeners/                          # 筛选器代码目录
│   ├── base_screener.py              # 筛选器基类（所有筛选器继承此类）
│   ├── coffee_cup_screener.py         # 咖啡杯形态筛选器
│   ├── coffee_cup_screener_v4.py     # 咖啡杯形态 V4版本
│   ├── jin_feng_huang_screener.py    # 涨停金凤凰
│   ├── yin_feng_huang_screener.py    # 涨停银凤凰
│   ├── shi_pan_xian_screener.py     # 涨停试盘线
│   ├── er_ban_hui_tiao_screener.py  # 二板回调
│   ├── zhang_ting_bei_liang_yin_screener.py  # 涨停倍量阴
│   ├── breakout_20day_screener.py   # 20日突破
│   ├── breakout_main_screener.py     # 主升浪突破
│   ├── daily_hot_cold_screener.py   # 每日冷热
│   ├── shuang_shou_ban_screener.py  # 双首板
│   └── ashare_21_screener.py        # A股2.1综合
│
├── config/screeners/                  # 筛选器配置文件目录
│   ├── coffee_cup.json               # 咖啡杯配置
│   ├── coffee_cup_v4.json           # 咖啡杯 V4配置
│   ├── jin_feng_huang.json          # 涨停金凤凰配置
│   └── ... (每个筛选器对应一个JSON文件)
│
├── backend/
│   ├── screeners.py                 # 筛选器发现和执行模块
│   └── app.py                      # Flask应用主文件
│
└── scripts/
    ├── run_all_screeners.py        # 运行所有筛选器
    └── test_all_screeners.py       # 测试所有筛选器
```

### 筛选器基类 (BaseScreener)

所有筛选器必须继承 `base_screener.py` 中的 `BaseScreener` 类，并实现以下方法：

```python
from base_screener import BaseScreener

class MyScreener(BaseScreener):
    def __init__(self, db_path: str = "data/stock_data.db", **kwargs):
        super().__init__(
            screener_name='my_screener',  # 筛选器唯一名称
            db_path=db_path,
            **kwargs
        )
        # 初始化参数
        self.my_param = 100
    
    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回筛选器的参数Schema（用于Dashboard配置界面）"""
        return {
            'MY_PARAM': {
                'type': 'int',
                'default': 100,
                'min': 50,
                'max': 200,
                'display_name': '我的参数',
                'description': '参数描述',
                'group': '基础设置'
            }
        }
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票的核心逻辑"""
        # 获取历史数据
        df = self.get_stock_data(code, days=200)
        if df is None or len(df) < 100:
            return None
        
        # 实现筛选逻辑
        if self._check_pattern(df):
            return {
                'code': code,
                'name': name,
                'close': df.iloc[-1]['close'],
                # ... 其他字段
            }
        return None
```

---

## 添加新筛选器

### 步骤 1: 创建筛选器代码

在 `screeners/` 目录下创建新文件：

```bash
# 示例：创建新高点筛选器
touch screeners/new_high_screener.py
```

### 步骤 2: 实现筛选器类

```python
#!/usr/bin/env python3
"""
新高点筛选器示例
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from typing import Optional, Dict, List
import logging

from base_screener import BaseScreener

logger = logging.getLogger(__name__)


class NewHighScreener(BaseScreener):
    """新高点筛选器"""
    
    def __init__(self, db_path: str = "data/stock_data.db", **kwargs):
        super().__init__(
            screener_name='new_high',
            db_path=db_path,
            **kwargs
        )
        
        # 加载配置参数
        config = self._load_config()
        if config:
            self.lookback_days = config.get('LOOKBACK_DAYS', 252)
        else:
            self.lookback_days = 252  # 默认1年
    
    def _load_config(self) -> Optional[Dict]:
        """从JSON配置文件加载参数"""
        from pathlib import Path
        import json
        
        config_path = Path(__file__).parent.parent / 'config' / 'screeners' / 'new_high.json'
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            params = config.get('parameters', {})
            return {
                'LOOKBACK_DAYS': params.get('LOOKBACK_DAYS', {}).get('value', 252),
                'MIN_RISE_PCT': params.get('MIN_RISE_PCT', {}).get('value', 50),
            }
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return None
    
    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回参数Schema"""
        return {
            'LOOKBACK_DAYS': {
                'type': 'int',
                'default': 252,
                'min': 100,
                'max': 500,
                'display_name': '回溯天数',
                'description': '计算新高的时间窗口（天）',
                'group': '基础设置'
            },
            'MIN_RISE_PCT': {
                'type': 'float',
                'default': 50.0,
                'min': 20.0,
                'max': 100.0,
                'step': 5.0,
                'display_name': '最小涨幅（%）',
                'description': '相对低点最少涨幅',
                'group': '筛选条件'
            }
        }
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=self.lookback_days)
        if df is None or len(df) < self.lookback_days:
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 检查是否创一年新高
        current_price = df.iloc[-1]['close']
        year_high = df.iloc[-self.lookback_days:]['high'].max()
        
        if current_price >= year_high * 0.99:  # 允许1%误差
            # 计算涨幅
            year_low = df.iloc[-self.lookback_days:]['low'].min()
            rise_pct = (current_price - year_low) / year_low * 100
            
            if rise_pct >= self.params.get('MIN_RISE_PCT', 50):
                return {
                    'code': code,
                    'name': name,
                    'close': round(current_price, 2),
                    'year_high': round(year_high, 2),
                    'rise_pct': round(rise_pct, 2),
                    'days_high': len(df)
                }
        
        return None
```

### 步骤 3: 创建配置文件

```bash
# 在 config/screeners/ 目录下创建配置文件
touch config/screeners/new_high.json
```

```json
{
  "metadata": {
    "version": "v1.0",
    "last_updated": "2026-04-13T14:00:00",
    "updated_by": "system",
    "description": "新高点筛选器配置"
  },
  "display_name": "新高点筛选器",
  "description": "筛选创一年新高且涨幅达标的股票",
  "category": "趋势跟踪",
  "parameters": {
    "LOOKBACK_DAYS": {
      "type": "int",
      "value": 252,
      "default": 252,
      "min": 100,
      "max": 500,
      "description": "计算新高的时间窗口（天）",
      "display_name": "回溯天数",
      "group": "基础设置"
    },
    "MIN_RISE_PCT": {
      "type": "float",
      "value": 50.0,
      "default": 50.0,
      "min": 20.0,
      "max": 100.0,
      "step": 5.0,
      "description": "相对低点最少涨幅",
      "display_name": "最小涨幅（%）",
      "group": "筛选条件"
    }
  }
}
```

### 步骤 4: 更新筛选器发现机制

在 `backend/screeners.py` 中，筛选器会自动发现。确保新筛选器文件名符合规范：

```python
# 筛选器文件名格式: {screener_name}_screener.py
# 例如: new_high_screener.py → screener_name = 'new_high'
```

如果筛选器需要被自动发现，确保：

1. 文件名以 `_screener.py` 结尾
2. 类名格式：`{CamelCaseName}Screener`
3. 文件位于 `screeners/` 目录

### 步骤 5: 测试筛选器

```bash
# 测试单个筛选器
python3 screeners/new_high_screener.py --date 2026-04-13

# 运行所有筛选器测试
python3 scripts/test_all_screeners.py
```

### ⚠️ 是否需要重启后台服务？

**答案：通常不需要**

- Flask 会动态加载筛选器
- 配置文件修改后立即生效（无需重启）
- 只有以下情况需要重启 Flask：

| 场景 | 需要重启 | 原因 |
|------|----------|------|
| 修改筛选器代码 | ✅ 需要重启 | Python 模块缓存 |
| 修改配置文件参数值 | ❌ 不需要 | 配置文件每次读取 |
| 添加新筛选器文件 | ✅ 需要重启 | 需要重新发现模块 |
| 修改 `backend/screeners.py` | ✅ 需要重启 | 核心模块变更 |
| 修改 `base_screener.py` | ✅ 需要重启 | 基类变更 |

### 重启 Flask 服务

```bash
# 方法1: 使用服务管理脚本
bash scripts/restart_flask.sh

# 方法2: 手动重启
# 停止当前服务
pkill -f "python.*app.py"

# 启动服务
cd backend
python3 app.py --port 8765
```

---

## 修改现有筛选器

### 修改筛选器参数

**无需重启！**

直接修改配置文件：

```bash
# 编辑配置文件
vi config/screeners/coffee_cup_v4.json

# 修改参数值，例如：
"RIM_INTERVAL_MIN": {
  "value": 35  # 从45改为35
}
```

配置文件修改后，下次运行筛选器时自动生效。

### 修改筛选器代码逻辑

**需要重启 Flask 服务**

```bash
# 1. 修改代码
vi screeners/coffee_cup_screener_v4.py

# 2. 重启 Flask
bash scripts/restart_flask.sh

# 3. 验证修改
python3 screeners/coffee_cup_screener_v4.py --date 2026-04-13
```

### 修改参数 Schema

**需要重启 Flask 服务**

如果添加新参数或修改参数定义（type, min, max等），需要重启以更新 Dashboard 配置界面。

---

## 删除筛选器

### 步骤 1: 备份（可选但推荐）

```bash
# 备份代码
mv screeners/my_screener.py screeners/my_screener.py.bak

# 备份配置
mv config/screeners/my_screener.json config/screeners/my_screener.json.bak
```

### 步骤 2: 删除文件

```bash
# 删除筛选器代码
rm screeners/my_screener.py

# 删除配置文件
rm config/screeners/my_screener.json

# 删除历史数据（可选）
rm -rf data/screeners/my_screener/
```

### 步骤 3: 重启 Flask 服务

```bash
bash scripts/restart_flask.sh
```

### 步骤 4: 更新文档

删除筛选器后，需要更新以下文档：

1. **TECHNICAL_DOCS/09_SCREENERS_GUIDE.md** - 移除该筛选器的说明
2. **TECHNICAL_DOCS/99_INDEX.md** - 更新索引
3. **scripts/run_all_screeners.py** - 从列表中移除（如果硬编码）

### ⚠️ 注意事项

- 删除前确认没有其他依赖此筛选器的代码
- 如果有历史数据需要保留，请先备份 `data/screeners/{screener_name}/` 目录
- 删除操作不可逆，请谨慎操作

---

## 服务重启指南

### Flask 服务管理

```bash
# 检查服务状态
ps aux | grep "python.*app.py"

# 重启服务
bash scripts/restart_flask.sh

# 手动停止
pkill -f "python.*app.py"

# 手动启动
cd backend
python3 app.py --port 8765
```

### Launchd 服务管理（macOS）

```bash
# 查看服务状态
launchctl list | grep neo

# 停止服务
launchctl stop com.neo.trade

# 启动服务
launchctl start com.neo.trade

# 重启服务
launchctl restart com.neo.trade

# 查看服务日志
tail -f ~/Library/Logs/com.neo.trade/output.log
```

### 重启时机总结

| 操作类型 | 需要重启 | 命令 |
|---------|----------|------|
| 修改配置参数 | ❌ | 无需操作 |
| 修改筛选器代码 | ✅ | `bash scripts/restart_flask.sh` |
| 添加新筛选器 | ✅ | `bash scripts/restart_flask.sh` |
| 删除筛选器 | ✅ | `bash scripts/restart_flask.sh` |
| 修改 base_screener.py | ✅ | `bash scripts/restart_flask.sh` |
| 修改 backend/screeners.py | ✅ | `bash scripts/restart_flask.sh` |
| 修改 backend/app.py | ✅ | `bash scripts/restart_flask.sh` |

---

## 文档更新流程

### 何时需要更新文档

1. **添加新筛选器后**
   - 更新 `TECHNICAL_DOCS/09_SCREENERS_GUIDE.md`
   - 更新 `TECHNICAL_DOCS/99_INDEX.md`
   - 可选：创建筛选器专用文档（如 `TECHNICAL_DOCS/16_NEW_HIGH.md`）

2. **修改筛选器参数后**
   - 如果参数结构变化，更新 `TECHNICAL_DOCS/04_SCREENING_CONFIG.md`
   - 如果只是数值调整，无需更新文档

3. **删除筛选器后**
   - 从 `TECHNICAL_DOCS/09_SCREENERS_GUIDE.md` 移除
   - 从 `TECHNICAL_DOCS/99_INDEX.md` 移除
   - 归档相关文档到 `TECHNICAL_DOCS/ARCHIVE/`

### 文档更新检查清单

添加新筛选器时：
- [ ] 筛选器代码已创建并测试通过
- [ ] 配置文件已创建
- [ ] `09_SCREENERS_GUIDE.md` 已更新
- [ ] `99_INDEX.md` 已更新
- [ ] 如有专用文档，已创建或更新
- [ ] Flask 服务已重启（如需要）

修改筛选器参数时：
- [ ] 配置文件已修改
- [ ] 如果参数Schema变化，已更新 `04_SCREENING_CONFIG.md`
- [ ] 已验证筛选器正常工作
- [ ] 无需重启服务（除非修改了Schema）

删除筛选器时：
- [ ] 确认无依赖后删除文件
- [ ] `09_SCREENERS_GUIDE.md` 已更新
- [ ] `99_INDEX.md` 已更新
- [ ] 相关文档已归档
- [ ] Flask 服务已重启

---

## 常见问题

### Q1: 修改配置文件后参数没有生效？

**A**: 确保配置文件格式正确：

```bash
# 验证JSON格式
python3 -m json.tool config/screeners/my_screener.json

# 检查筛选器是否正确加载配置
python3 -c "
from screeners.my_screener import MyScreener
s = MyScreener()
print(f'MY_PARAM = {s.my_param}')
"
```

### Q2: 新添加的筛选器没有出现在 Dashboard 中？

**A**: 检查以下几点：

1. 文件名格式：`{name}_screener.py`
2. 类名格式：`{CamelCaseName}Screener`
3. 实现了 `get_parameter_schema()` 方法
4. Flask 服务已重启
5. 配置文件存在于 `config/screeners/`

### Q3: 重启 Flask 服务后访问不通？

**A**: 检查服务状态：

```bash
# 检查进程
ps aux | grep "python.*app.py"

# 检查端口占用
lsof -i :8765

# 查看日志
tail -f logs/dashboard.log
```

### Q4: 如何批量更新多个筛选器的配置？

**A**: 编写脚本批量处理：

```python
# scripts/batch_update_config.py
import json
from pathlib import Path

config_dir = Path('config/screeners')
update_config = {'CUP_DEPTH_MIN': 0.03}  # 要更新的参数

for config_file in config_dir.glob('*.json'):
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # 更新特定参数
    if 'CUP_DEPTH_MIN' in config.get('parameters', {}):
        config['parameters']['CUP_DEPTH_MIN']['value'] = update_config['CUP_DEPTH_MIN']
        
        # 保存
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"Updated: {config_file.name}")
```

### Q5: 筛选器运行速度慢怎么办？

**A**: 优化建议：

1. **减少历史数据天数**：只在 `get_stock_data()` 中请求必要天数
2. **使用向量化操作**：用 pandas/numpy 替代循环
3. **添加缓存**：对重复计算结果缓存
4. **批量处理**：优化数据库查询，减少单次查询次数

---

## 附录：当前筛选器列表

| 筛选器名称 | 文件名 | 配置文件 | 状态 |
|----------|--------|----------|------|
| 咖啡杯形态 | coffee_cup_screener.py | coffee_cup.json | ✅ |
| 咖啡杯形态V4 | coffee_cup_screener_v4.py | coffee_cup_v4.json | ✅ |
| 涨停金凤凰 | jin_feng_huang_screener.py | jin_feng_huang.json | ✅ |
| 涨停银凤凰 | yin_feng_huang_screener.py | yin_feng_huang.json | ✅ |
| 涨停试盘线 | shi_pan_xian_screener.py | shi_pan_xian.json | ✅ |
| 二板回调 | er_ban_hui_tiao_screener.py | er_ban_hui_tiao.json | ✅ |
| 涨停倍量阴 | zhang_ting_bei_liang_yin_screener.py | zhang_ting_bei_liang_yin.json | ✅ |
| 20日突破 | breakout_20day_screener.py | breakout_20day.json | ✅ |
| 主升浪突破 | breakout_main_screener.py | breakout_main.json | ✅ |
| 每日冷热 | daily_hot_cold_screener.py | daily_hot_cold.json | ✅ |
| 双首板 | shuang_shou_ban_screener.py | shuang_shou_ban.json | ✅ |
| A股2.1综合 | ashare_21_screener.py | ashare_21.json | ✅ |

---

**文档版本**: v1.0  
**最后更新**: 2026-04-13  
**维护者**: NeoTrade2 技术团队
