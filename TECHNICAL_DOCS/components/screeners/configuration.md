# 筛选器配置系统 - 开发文档

**项目名称**: NeoTrade2 筛选器配置管理系统
**创建时间**: 2026-04-04
**版本**: v1.0
**目标**: 为所有筛选器提供可视化的参数配置、描述编辑、版本管理和即时生效功能

---

## 📋 项目概述

### 问题背景
- 当前筛选器的参数硬编码在Python文件中
- 修改参数需要直接编辑代码，容易出错
- 没有版本管理，无法回滚
- 筛选器定义和描述分散，难以维护
- 业务团队无法直观查看和调整参数

### 解决方案
- 配置外部化到JSON文件
- 参数定义与代码分离
- 前端可视化配置界面
- 数据库版本管理和回滚
- 自动更新代码注释（docstring）

### 核心目标
1. **即时生效**: 修改配置后立即生效，无需重启服务
2. **版本管理**: 支持配置版本保存和回滚
3. **参数验证**: 自动验证参数范围和类型
4. **通用性**: 适用于所有14个筛选器
5. **文档同步**: 配置描述自动同步到代码注释

---

## 🏗️ 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (React + TypeScript)                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  筛选器配置页面                                       │ │
│  │  - 筛选器列表和搜索                                     │ │
│  │  - 参数编辑器（表单）                                   │ │
│  │  - 描述编辑器（富文本）                                 │ │
│  │  - 版本历史和回滚                                       │ │
│  │  - 参数验证和预览                                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          ↓ API                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                        后端 (Flask + Python)                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  筛选器配置管理 API (screener_config.py)                 │ │
│  │  - GET  /api/screeners/config/<name>                    │ │
│  │  - PUT  /api/screeners/config/<name>                    │ │
│  │  - POST /api/screeners/config/<name>/validate             │ │
│  │  - POST /api/screeners/config/<name>/rollback            │ │
│  │  - GET  /api/screeners/config/<name>/versions             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  配置加载模块 (config_loader.py)                          │ │
│  │  - 从JSON文件加载配置                                    │ │
│  │  - 参数验证                                              │ │
│  │  - 版本管理                                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  数据库 (SQLite)                                         │ │
│  │  - screener_configs (当前配置)                          │ │
│  │  - screener_config_history (版本历史)                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  筛选器实例 (BaseScreener)                              │ │
│  │  - 从配置文件加载参数                                     │ │
│  │  - 参数即时生效                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                      配置文件 (JSON)                            │
│  config/screeners/                                           │
│  ├── coffee_cup.json                                        │
│  ├── jin_feng_huang.json                                    │
│  ├── yin_feng_huang.json                                    │
│  ├── shi_pan_xian.json                                     │
│  ├── er_ban_hui_tiao.json                                   │
│  ├── zhang_ting_bei_liang_yin.json                          │
│  ├── breakout_20day.json                                    │
│  ├── breakout_main.json                                      │
│  ├── daily_hot_cold.json                                    │
│  ├── shuang_shou_ban.json                                   │
│  └── ashare_21.json                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
NeoTrade2/
├── config/
│   └── screeners/                    # 筛选器配置文件目录
│       ├── coffee_cup.json
│       ├── jin_feng_huang.json
│       ├── yin_feng_huang.json
│       ├── shi_pan_xian.json
│       ├── er_ban_hui_tiao.json
│       ├── zhang_ting_bei_liang_yin.json
│       ├── breakout_20day.json
│       ├── breakout_main.json
│       ├── daily_hot_cold.json
│       ├── shuang_shou_ban.json
│       └── ashare_21.json
│
├── backend/
│   ├── models.py                    # 数据库模型（新增配置相关表）
│   ├── screener_config.py           # 筛选器配置管理API（新建）
│   ├── config_loader.py             # 配置加载模块（新建）
│   ├── docstring_updater.py         # Docstring更新模块（新建）
│   └── validators.py                # 参数验证器（扩展）
│
├── screeners/
│   ├── base_screener.py             # 基类改造（支持配置加载）
│   └── *_screener.py               # 各筛选器（改造为使用配置）
│
├── frontend/src/
│   ├── components/
│   │   └── ScreenerConfigEditor.tsx  # 筛选器配置编辑器（新建）
│   └── pages/
│       └── ScreenerManagement.tsx    # 筛选器管理页面（新建）
│
└── data/
    └── dashboard.db                 # 新增配置相关表
```

---

## 🗄️ 数据库设计

### 表1: screener_configs (当前配置)

```sql
CREATE TABLE IF NOT EXISTS screener_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screener_name TEXT UNIQUE NOT NULL,           -- 筛选器名称
    display_name TEXT NOT NULL,                    -- 显示名称
    description TEXT,                               -- 描述
    category TEXT,                                  -- 分类
    config_json TEXT NOT NULL,                     -- 完整配置JSON
    config_schema TEXT NOT NULL,                    -- 参数Schema (从类方法获取)
    current_version TEXT DEFAULT 'v1.0',           -- 当前版本号
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_screener_configs_name ON screener_configs(screener_name);
```

### 表2: screener_config_history (版本历史)

```sql
CREATE TABLE IF NOT EXISTS screener_config_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screener_name TEXT NOT NULL,                   -- 筛选器名称
    version TEXT NOT NULL,                          -- 版本号
    config_json TEXT NOT NULL,                      -- 完整配置JSON
    config_schema TEXT NOT NULL,                     -- 参数Schema
    change_summary TEXT,                             -- 变更摘要
    changed_by TEXT,                                  -- 修改人
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (screener_name) REFERENCES screener_configs(screener_name)
);

CREATE INDEX IF NOT EXISTS idx_screener_config_history_name ON screener_config_history(screener_name);
CREATE INDEX IF NOT EXISTS idx_screener_config_history_version ON screener_config_history(screener_name, version);
```

---

## ⚙️ 配置文件格式

### 通用配置模板

```json
{
  "metadata": {
    "version": "v1.0",
    "last_updated": "2026-04-04T12:00:00",
    "updated_by": "bruce"
  },
  "display_name": "二板回调",
  "description": "寻找二连涨停后回调不破首板开盘价，然后启动的股票",
  "category": "主力启动信号",
  "parameters": {
    "limit_days": {
      "type": "int",
      "value": 14,
      "default": 14,
      "min": 1,
      "max": 60,
      "description": "时间范围（交易日）",
      "display_name": "时间范围（天）",
      "group": "基础设置"
    },
    "limit_up_threshold": {
      "type": "float",
      "value": 9.9,
      "default": 9.9,
      "min": 0,
      "max": 20,
      "step": 0.1,
      "description": "涨停阈值（%）",
      "display_name": "涨停阈值（%）",
      "group": "信号条件"
    },
    "first_amount_ratio": {
      "type": "float",
      "value": 2.0,
      "default": 2.0,
      "min": 1.0,
      "max": 10.0,
      "step": 0.1,
      "description": "首板成交额倍数",
      "display_name": "首板成交额倍数",
      "group": "信号条件"
    },
    "allow_tolerance": {
      "type": "float",
      "value": 0.01,
      "default": 0.01,
      "min": 0.0,
      "max": 0.05,
      "step": 0.001,
      "description": "价格容忍误差（0-1）",
      "display_name": "价格容忍误差",
      "group": "信号条件"
    }
  }
}
```

### 参数类型定义

| 类型 | 说明 | 验证规则 |
|------|------|---------|
| `int` | 整数 | min ≤ value ≤ max |
| `float` | 浮点数 | min ≤ value ≤ max, 按step步进 |
| `bool` | 布尔值 | true/false |
| `string` | 字符串 | 非空，可定义正则表达式 |

### 参数分组

| 分组名 | 用途 |
|--------|------|
| 基础设置 | 时间范围、数据范围等通用参数 |
| 信号条件 | 各种阈值、倍数等信号判断参数 |
| 过滤条件 | 股票过滤参数（市值、ST等） |
| 输出设置 | 结果展示、格式化参数 |

---

## 🔌 API 设计

### 1. 获取筛选器配置

```
GET /api/screeners/config/<name>

Response:
{
  "success": true,
  "screener_name": "er_ban_hui_tiao",
  "display_name": "二板回调",
  "description": "...",
  "category": "主力启动信号",
  "metadata": {
    "version": "v1.0",
    "last_updated": "2026-04-04T12:00:00",
    "updated_by": "bruce"
  },
  "parameters": {
    "limit_days": {
      "type": "int",
      "value": 14,
      "default": 14,
      "min": 1,
      "max": 60,
      "description": "时间范围（交易日）",
      "display_name": "时间范围（天）",
      "group": "基础设置"
    },
    ...
  }
}
```

### 2. 更新筛选器配置

```
PUT /api/screeners/config/<name>

Request Body:
{
  "display_name": "二板回调",
  "description": "...",
  "category": "主力启动信号",
  "parameters": {
    "limit_days": {
      "value": 20
    },
    ...
  },
  "change_summary": "调整时间范围为20天",
  "updated_by": "bruce"
}

Response:
{
  "success": true,
  "version": "v1.1",
  "message": "配置已保存，版本更新为 v1.1"
}
```

### 3. 验证配置参数

```
POST /api/screeners/config/<name>/validate

Request Body:
{
  "parameters": {
    "limit_days": {
      "value": 999
    },
    ...
  }
}

Response:
{
  "success": false,
  "errors": {
    "limit_days": "值必须在1-60之间，当前值: 999"
  }
}
```

### 4. 获取版本历史

```
GET /api/screeners/config/<name>/versions

Response:
{
  "success": true,
  "versions": [
    {
      "version": "v1.1",
      "created_at": "2026-04-04T14:00:00",
      "changed_by": "bruce",
      "change_summary": "调整时间范围为20天"
    },
    {
      "version": "v1.0",
      "created_at": "2026-04-04T12:00:00",
      "changed_by": "system",
      "change_summary": "初始版本"
    }
  ]
}
```

### 5. 回滚到指定版本

```
POST /api/screeners/config/<name>/rollback

Request Body:
{
  "version": "v1.0"
}

Response:
{
  "success": true,
  "message": "已回滚到 v1.0",
  "current_version": "v1.0"
}
```

### 6. 应用配置到代码

```
POST /api/screeners/config/<name>/apply

Request Body:
{
  "update_docstring": true
}

Response:
{
  "success": true,
  "message": "配置已应用到代码",
  "docstring_updated": true
}
```

---

## 🎨 前端设计

### 页面结构

```
Dashboard → 筛选器管理

筛选器列表页:
┌─────────────────────────────────────────────────────────┐
│  筛选器管理                              [+ 新建]         │
├─────────────────────────────────────────────────────────┤
│  搜索: [搜索框...]  分类: [全部 ▼]                   │
├─────────────────────────────────────────────────────────┤
│  筛选器名称          分类        最后更新    操作       │
│  ─────────────────────────────────────────────────────  │
│  二板回调          主力启动信号  2026-04-04  [配置]    │
│  涨停金凤凰        主力启动信号  2026-04-04  [配置]    │
│  涨停银凤凰        主力启动信号  2026-04-04  [配置]    │
│  涨停试盘线        主力启动信号  2026-04-04  [配置]    │
│  涨停倍量阴        主力启动信号  2026-04-04  [配置]    │
│  咖啡杯            形态识别      2026-04-03  [配置]    │
│  ...                                            │
└─────────────────────────────────────────────────────────┘
```

### 配置编辑页面

```
┌─────────────────────────────────────────────────────────────────┐
│  二板回调 - 配置                              [← 返回] [保存] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  基本信息                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 显示名称: [二板回调                           ]      │   │
│  │ 分    类: [主力启动信号 ▼]                            │   │
│  │ 描    述: [寻找二连涨停后回调不破首板开盘价...    ]│   │
│  │           [                                  ]          │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  参数配置                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 基础设置                                              │   │
│  │  时间范围（天）: [14     ]  (1-60)      [↔ 重置]   │   │
│  │                                                      │   │
│  │ 信号条件                                              │   │
│  │  涨停阈值（%）: [9.9    ]  (0-20, 步进0.1)  [↔ 重置]   │   │
│  │  首板成交额倍数: [2.0    ]  (1.0-10.0, 步进0.1)        │   │
│  │  价格容忍误差:   [0.01   ]  (0.0-0.05, 步进0.001)    │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  版本历史                                          [查看全部]  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ v1.0 (当前)  - 2026-04-04 12:00  by bruce              │   │
│  │             初始版本                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  操作                                                          │
│  [预览效果] [应用到代码] [重置为默认] [查看完整配置]         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 组件设计

#### 1. 参数编辑器 (ParameterEditor)

```typescript
interface ParameterEditorProps {
  parameter: ParameterConfig;
  value: any;
  onChange: (value: any) => void;
  onReset: () => void;
}

// 根据type动态渲染输入组件
// - int/float: InputNumber
// - bool: Switch
// - string: TextArea
// - 带验证和错误提示
```

#### 2. 版本历史 (VersionHistory)

```typescript
interface VersionHistoryProps {
  screenerName: string;
  currentVersion: string;
  onRollback: (version: string) => void;
  onViewAll: () => void;
}

// 显示最近的3个版本
// 点击"查看全部"打开模态框显示所有版本
// 每个版本显示：版本号、时间、修改人、变更摘要、回滚按钮
```

#### 3. 配置验证 (ConfigValidator)

```typescript
interface ConfigValidatorProps {
  schema: ParameterSchema;
  config: Record<string, any>;
  onValidate: (valid: boolean, errors: Record<string, string>) => void;
}

// 实时验证参数
// 在参数变化时触发
// 显示验证错误（红色边框、错误提示）
```

---

## 🔧 筛选器代码改造

### 1. BaseScreener 改造

```python
# screeners/base_screener.py (新增方法)

class BaseScreener(ABC):
    def __init__(self, screener_name: str, config_path: str = None, **kwargs):
        self.screener_name = screener_name
        
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 从配置读取参数到实例变量
        self._apply_config_parameters()
        
        # 原有初始化...
    
    def _load_config(self, config_path: str = None) -> Dict:
        """加载筛选器配置"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'screeners' / f'{self.screener_name}.json'
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return self._get_default_config()
    
    def _apply_config_parameters(self):
        """从配置读取参数到实例变量"""
        parameters = self.config.get('parameters', {})
        for param_name, param_config in parameters.items():
            setattr(self, param_name, param_config['value'])
    
    def _get_default_config(self) -> Dict:
        """子类可以重写，提供默认配置"""
        return {
            'display_name': self.screener_name,
            'description': '',
            'category': '未分类',
            'parameters': {}
        }
    
    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """
        子类重写，定义支持的参数和验证规则
        
        返回格式:
        {
            'limit_days': {
                'type': 'int',
                'default': 14,
                'min': 1,
                'max': 60,
                'description': '时间范围',
                'display_name': '时间范围（天）',
                'group': '基础设置'
            },
            ...
        }
        """
        return {}
```

### 2. 筛选器改造示例

```python
# screeners/er_ban_hui_tiao_screener.py (改造后)

class ErBanHuiTiaoScreener(BaseScreener):
    """二板回调筛选器 V3（支持配置）"""
    
    def __init__(self, config_path: str = None, **kwargs):
        super().__init__(screener_name='er_ban_hui_tiao', config_path=config_path, **kwargs)
        
        # 配置参数已自动加载到实例变量
        # self.limit_days
        # self.limit_up_threshold
        # self.first_amount_ratio
        # self.allow_tolerance
    
    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """定义该筛选器支持的参数"""
        return {
            'limit_days': {
                'type': 'int',
                'default': 14,
                'min': 1,
                'max': 60,
                'description': '时间范围（交易日）',
                'display_name': '时间范围（天）',
                'group': '基础设置'
            },
            'limit_up_threshold': {
                'type': 'float',
                'default': 9.9,
                'min': 0,
                'max': 20,
                'step': 0.1,
                'description': '涨停阈值（%）',
                'display_name': '涨停阈值（%）',
                'group': '信号条件'
            },
            'first_amount_ratio': {
                'type': 'float',
                'default': 2.0,
                'min': 1.0,
                'max': 10.0,
                'step': 0.1,
                'description': '首板成交额倍数',
                'display_name': '首板成交额倍数',
                'group': '信号条件'
            },
            'allow_tolerance': {
                'type': 'float',
                'default': 0.01,
                'min': 0.0,
                'max': 0.05,
                'step': 0.001,
                'description': '价格容忍误差（0-1）',
                'display_name': '价格容忍误差',
                'group': '信号条件'
            }
        }
    
    def is_limit_up(self, pct_change: float) -> bool:
        """判断是否涨停（使用配置的阈值）"""
        return pct_change >= self.limit_up_threshold
    
    def check_signal_two(self, df: pd.DataFrame, signal_one: Dict, current_idx: int) -> bool:
        """检查信号二：二连板后到当前日，所有交易日最低价 ≥ 首板开盘价"""
        second_idx = signal_one['second_idx']
        first_open = signal_one['first_open']
        
        for i in range(second_idx + 1, current_idx):
            if i >= len(df):
                break
            day_low = df.iloc[i]['low']
            if day_low < first_open * (1 - self.allow_tolerance):  # 使用配置的容忍误差
                return False
        
        return True
    
    # 其他方法使用配置参数...
```

### 3. 配置文件生成脚本

创建工具脚本自动生成初始配置文件：

```python
# scripts/generate_screener_configs.py

def generate_config_from_screener(screener_name: str, screener_class: type):
    """从筛选器类生成配置文件"""
    schema = screener_class.get_parameter_schema()
    
    config = {
        'metadata': {
            'version': 'v1.0',
            'last_updated': datetime.now().isoformat(),
            'updated_by': 'system'
        },
        'display_name': screener_class.__doc__.split('\n')[0].strip(),
        'description': screener_class.__doc__.strip(),
        'category': '未分类',
        'parameters': {}
    }
    
    # 从schema生成parameters
    for param_name, param_schema in schema.items():
        config['parameters'][param_name] = {
            'type': param_schema['type'],
            'value': param_schema['default'],
            'default': param_schema['default'],
            'min': param_schema.get('min'),
            'max': param_schema.get('max'),
            'step': param_schema.get('step'),
            'description': param_schema['description'],
            'display_name': param_schema['display_name'],
            'group': param_schema.get('group', '其他')
        }
    
    return config

def generate_all_configs():
    """为所有筛选器生成配置文件"""
    screeners = [
        'coffee_cup', 'jin_feng_huang', 'yin_feng_huang',
        'shi_pan_xian', 'er_ban_hui_tiao', 'zhang_ting_bei_liang_yin',
        'breakout_20day', 'breakout_main', 'daily_hot_cold',
        'shuang_shou_ban', 'ashare_21'
    ]
    
    for screener_name in screeners:
        # 动态导入筛选器类
        module = importlib.import_module(f'screeners.{screener_name}_screener')
        screener_class = getattr(module, f'{screener_name.title().replace("_", "")}Screener')
        
        # 生成配置
        config = generate_config_from_screener(screener_name, screener_class)
        
        # 保存到文件
        config_path = Path('config/screeners') / f'{screener_name}.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"Generated config: {config_path}")
```

---

## 📝 实施计划

### Phase 1: 基础架构 (2-3天)

**任务清单:**
1. [ ] 创建数据库表（screener_configs, screener_config_history）
2. [ ] 创建配置加载模块 (`config_loader.py`)
3. [ ] 创建参数验证器 (`validators.py` 扩展)
4. [ ] 创建Docstring更新模块 (`docstring_updater.py`)
5. [ ] 修改 `base_screener.py` 支持配置加载
6. [ ] 测试配置加载功能

**验证标准:**
- [ ] 数据库表创建成功
- [ ] 配置文件可以正确加载
- [ ] 参数验证功能正常
- [ ] Docstring可以正确更新

### Phase 2: 筛选器配置创建 (1天)

**任务清单:**
1. [ ] 创建配置生成脚本 (`generate_screener_configs.py`)
2. [ ] 为所有14个筛选器定义参数schema
3. [ ] 运行脚本生成所有配置文件
4. [ ] 验证配置文件格式正确

**筛选器列表:**
- coffee_cup
- jin_feng_huang
- yin_feng_huang
- shi_pan_xian
- er_ban_hui_tiao
- zhang_ting_bei_liang_yin
- breakout_20day
- breakout_main
- daily_hot_cold
- shuang_shou_ban
- ashare_21
- double_bottom
- ascending_triangle
- high_tight_flag

**验证标准:**
- [ ] 所有14个配置文件生成成功
- [ ] 配置文件包含正确的参数定义
- [ ] 配置文件可以正确读取

### Phase 3: 筛选器代码改造 (2-3天)

**任务清单:**
1. [ ] 改造 `base_screener.py`
2. [ ] 改造5个主力启动信号筛选器（优先）
3. [ ] 改造其余9个筛选器
4. [ ] 每个筛选器添加 `get_parameter_schema()` 方法
5. [ ] 测试筛选器可以从配置加载参数
6. [ ] 测试参数修改后立即生效

**改造优先级:**
1. **高优先级**（已完成更新文档的）:
   - er_ban_hui_tiao
   - jin_feng_huang
   - yin_feng_huang
   - shi_pan_xian
   - zhang_ting_bei_liang_yin

2. **中优先级**:
   - coffee_cup
   - daily_hot_cold
   - breakout_20day
   - breakout_main

3. **低优先级**:
   - shuang_shou_ban
   - ashare_21
   - double_bottom
   - ascending_triangle
   - high_tight_flag

**验证标准:**
- [ ] 所有筛选器可以从配置加载参数
- [ ] 参数修改后立即生效（无需重启）
- [ ] 筛选器逻辑正确使用配置参数
- [ ] 配置不存在的参数时使用默认值

### Phase 4: API实现 (1-2天)

**任务清单:**
1. [ ] 创建 `screener_config.py` 蓝图
2. [ ] 实现获取配置API
3. [ ] 实现更新配置API
4. [ ] 实现参数验证API
5. [ ] 实现版本历史API
6. [ ] 实现回滚API
7. [ ] 实现应用到代码API
8. [ ] 在 `app.py` 中注册蓝图
9. [ ] 测试所有API端点

**验证标准:**
- [ ] 所有API端点正常工作
- [ ] 参数验证正确
- [ ] 版本管理功能正常
- [ ] 回滚功能正常

### Phase 5: 前端开发 (2-3天)

**任务清单:**
1. [ ] 创建筛选器管理页面 (`ScreenerManagement.tsx`)
2. [ ] 创建筛选器列表组件
3. [ ] 创建配置编辑器组件 (`ScreenerConfigEditor.tsx`)
4. [ ] 创建参数编辑器组件 (`ParameterEditor.tsx`)
5. [ ] 创建版本历史组件 (`VersionHistory.tsx`)
6. [ ] 实现参数验证UI
7. [ ] 实现配置保存和预览
8. [ ] 添加路由和导航
9. [ ] 测试所有功能

**验证标准:**
- [ ] 可以查看所有筛选器
- [ ] 可以编辑筛选器配置
- [ ] 参数验证实时生效
- [ ] 可以查看版本历史
- [ ] 可以回滚到指定版本
- [ ] 可以应用配置到代码

### Phase 6: 测试和优化 (1天)

**任务清单:**
1. [ ] 端到端测试完整流程
2. [ ] 测试参数修改后立即生效
3. [ ] 测试版本回滚
4. [ ] 测试Docstring更新
5. [ ] 测试所有14个筛选器
6. [ ] 性能优化（如有需要）
7. [ ] 修复发现的问题
8. [ ] 编写使用文档

**验证标准:**
- [ ] 完整流程无bug
- [ ] 所有筛选器都可以正常配置
- [ ] 参数修改后立即生效
- [ ] 版本管理功能稳定
- [ ] 文档完整

---

## 🧪 测试计划

### 单元测试

```python
# tests/test_config_loader.py

def test_load_config():
    """测试配置加载"""
    config = load_config('er_ban_hui_tiao')
    assert config['display_name'] == '二板回调'
    assert 'parameters' in config

def test_validate_parameters():
    """测试参数验证"""
    schema = get_parameter_schema('er_ban_hui_tiao')
    errors = validate_parameters({'limit_days': 999}, schema)
    assert 'limit_days' in errors

def test_version_management():
    """测试版本管理"""
    # 保存配置
    save_config('er_ban_hui_tiao', config_v1)
    
    # 更新配置
    save_config('er_ban_hui_tiao', config_v2)
    
    # 回滚
    rollback_config('er_ban_hui_tiao', 'v1.0')
    
    # 验证
    current = get_config('er_ban_hui_tiao')
    assert current['version'] == 'v1.0'
```

### 集成测试

```python
# tests/test_screener_config_integration.py

def test_config_apply_to_screener():
    """测试配置应用到筛选器"""
    # 修改配置
    config['parameters']['limit_days']['value'] = 20
    save_config('er_ban_hui_tiao', config)
    
    # 重新创建筛选器实例
    screener = ErBanHuiTiaoScreener()
    
    # 验证参数生效
    assert screener.limit_days == 20

def test_all_screeners_load_config():
    """测试所有筛选器可以加载配置"""
    screeners = get_all_screener_names()
    for name in screeners:
        screener = create_screener_instance(name)
        assert screener.config is not None
```

### 端到端测试

1. 打开筛选器管理页面
2. 选择一个筛选器
3. 修改参数并验证
4. 保存配置并验证
5. 查看版本历史
6. 回滚到上一版本
7. 应用配置到代码
8. 验证Python文件docstring已更新

---

## ⚠️ 风险和注意事项

### 1. 配置加载失败处理

**风险**: 配置文件不存在或损坏导致筛选器无法启动

**解决方案**:
```python
def _load_config(self, config_path: str = None) -> Dict:
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Config not found, using defaults")
        return self._get_default_config()
    except json.JSONDecodeError:
        logger.error(f"Config corrupted, using defaults")
        return self._get_default_config()
```

### 2. 参数类型安全

**风险**: 配置文件中参数类型错误

**解决方案**:
```python
def _apply_config_parameters(self):
    parameters = self.config.get('parameters', {})
    for param_name, param_config in parameters.items():
        value = param_config['value']
        param_type = param_config['type']
        
        # 类型转换
        if param_type == 'int':
            value = int(value)
        elif param_type == 'float':
            value = float(value)
        elif param_type == 'bool':
            value = bool(value)
        
        setattr(self, param_name, value)
```

### 3. 配置文件并发修改

**风险**: 多人同时修改配置导致冲突

**解决方案**:
- 数据库记录最后修改时间
- 保存前检查版本
- 使用乐观锁（version字段）

### 4. 参数修改后正在运行的筛选器

**风险**: 参数修改后正在运行的筛选器使用旧参数

**解决方案**:
- 新的筛选器实例使用新参数
- 已运行的实例继续使用旧参数
- 建议在参数修改后重新运行筛选器

### 5. Docstring更新失败

**风险**: Python文件正在使用，无法更新

**解决方案**:
- 捕获IOError
- 在日志中记录警告
- 不影响配置保存
- 下次启动时自动更新

---

## 📊 成功指标

- [ ] 所有14个筛选器支持配置
- [ ] 配置修改后立即生效
- [ ] 参数验证功能正常
- [ ] 版本管理功能正常
- [ ] 支持回滚到上一版本
- [ ] Docstring可以正确更新
- [ ] 前端界面友好易用
- [ ] 完整的测试覆盖

---

## 📚 相关文档

- [筛选器配置格式规范](#配置文件格式)
- [API接口文档](#api设计)
- [筛选器改造指南](#筛选器代码改造)
- [参数验证规则](#参数类型定义)

---

**文档版本**: v1.0
**最后更新**: 2026-04-04
**负责人**: 技术负责人 + AI
