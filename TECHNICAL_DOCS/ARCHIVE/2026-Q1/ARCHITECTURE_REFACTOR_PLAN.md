# 数据源切换与代码架构梳理方案

**日期**: 2026-03-19  
**背景**: 双数据源（本地Baostock + iFind实时）切换导致的一致性问题  
**目标**: 建立可维护、可扩展的架构基础

---

## 📊 当前问题诊断

### 1. 数据源现状
| 数据源 | 状态 | 到期时间 | 可靠性 |
|--------|------|----------|--------|
| Baostock (本地) | 生产中 | - | 低（经常断） |
| iFind (实时) | 测试中 | 2026-04-02 | 待定（可能付费） |

### 2. 代码层面问题
- **字符串/命名不一致**: code vs stock_code, name vs stock_name
- **返回值格式不统一**: 不同接口返回不同结构
- **文件名混乱**: 时间戳格式、路径不一致
- **缓存问题**: 没有标准缓存层，到处临时存储
- **错误处理缺失**: 没有统一的错误码和降级机制

### 3. 架构层面问题
- **前后端耦合**: 前端直接依赖后端具体实现
- **无抽象层**: 数据源直接暴露给业务逻辑
- **配置分散**: 配置硬编码在多处
- **测试缺失**: 没有自动化测试保障修改安全

---

## 🏗️ 重构方案

### 阶段一：建立数据抽象层 (本周)

#### 1.1 统一数据模型
```python
# models/schemas.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class StockData:
    """统一的股票数据模型"""
    code: str                    # 股票代码（统一格式：600000）
    name: str                    # 股票名称
    close: float                 # 收盘价
    change: float               # 涨跌额
    change_ratio: float         # 涨跌幅（%）
    volume: float               # 成交量
    amount: float               # 成交额
    timestamp: datetime         # 数据时间
    source: str                 # 数据来源：baostock/ifind
    
    # 可选字段
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    turnover: Optional[float] = None  # 换手率

@dataclass
class ScreenerResult:
    """统一的筛选结果模型"""
    screener_id: str
    screener_name: str
    run_date: str               # YYYY-MM-DD
    run_time: datetime
    stocks: List[StockData]
    total_checked: int
    data_source: str            # baostock/ifind
    
    # 元数据
    execution_time_ms: int
    error_message: Optional[str] = None
```

#### 1.2 数据源接口抽象
```python
# data/sources/base.py
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

class DataSource(ABC):
    """数据源抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass
    
    @abstractmethod
    def get_stock_data(self, code: str, date: Optional[str] = None) -> StockData:
        """获取单只股票数据"""
        pass
    
    @abstractmethod
    def get_all_stocks(self, date: Optional[str] = None) -> List[StockData]:
        """获取所有股票数据"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        pass

# data/sources/baostock_source.py
class BaostockSource(DataSource):
    """本地数据库数据源"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    @property
    def name(self) -> str:
        return "baostock"
    
    def get_all_stocks(self, date: Optional[str] = None) -> List[StockData]:
        # 从 SQLite 读取
        pass
    
    def is_available(self) -> bool:
        # 检查数据库连接
        pass

# data/sources/ifind_source.py
class IfindSource(DataSource):
    """iFind实时数据源"""
    
    def __init__(self, token: str):
        self.token = token
        self.client = IfindClient(token)
        
    @property
    def name(self) -> str:
        return "ifind"
    
    def get_all_stocks(self, date: Optional[str] = None) -> List[StockData]:
        # 调用 iFind API
        pass
    
    def is_available(self) -> bool:
        # 检查 token 有效期
        pass
```

#### 1.3 数据源管理器
```python
# data/source_manager.py
class DataSourceManager:
    """管理多个数据源，提供自动切换"""
    
    def __init__(self):
        self.sources: Dict[str, DataSource] = {}
        self.primary_source: Optional[str] = None
        self.fallback_source: Optional[str] = None
    
    def register(self, source: DataSource, primary: bool = False):
        """注册数据源"""
        self.sources[source.name] = source
        if primary:
            self.primary_source = source.name
    
    def get_data(self, code: str, date: Optional[str] = None) -> StockData:
        """获取数据（自动处理降级）"""
        # 先尝试主数据源
        if self.primary_source:
            source = self.sources[self.primary_source]
            if source.is_available():
                return source.get_stock_data(code, date)
        
        # 降级到备用数据源
        if self.fallback_source:
            source = self.sources[self.fallback_source]
            if source.is_available():
                return source.get_stock_data(code, date)
        
        raise DataSourceUnavailable("No data source available")
```

---

### 阶段二：标准化 API 响应 (本周)

#### 2.1 统一响应格式
```python
# api/responses.py
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class ApiResponse(Generic[T]):
    """统一 API 响应格式"""
    
    def __init__(
        self,
        success: bool,
        data: Optional[T] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.success = success
        self.data = data
        self.error_code = error_code
        self.error_message = error_message
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": {
                "code": self.error_code,
                "message": self.error_message
            } if not self.success else None,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }

# 错误码定义
class ErrorCode:
    SUCCESS = "SUCCESS"
    DATA_SOURCE_UNAVAILABLE = "DATA_SOURCE_UNAVAILABLE"
    INVALID_PARAMS = "INVALID_PARAMS"
    SCREENER_NOT_FOUND = "SCREENER_NOT_FOUND"
    DATABASE_ERROR = "DATABASE_ERROR"
    IFIND_API_ERROR = "IFIND_API_ERROR"
```

---

### 阶段三：前端架构优化 (下周)

#### 3.1 统一前端数据模型
```typescript
// src/types/stock.ts
interface StockData {
  code: string;
  name: string;
  close: number;
  change: number;
  changeRatio: number;
  volume: number;
  amount: number;
  timestamp: string;
  source: 'baostock' | 'ifind';
}

interface ScreenerRunResult {
  screenerId: string;
  screenerName: string;
  runDate: string;
  isRealtime: boolean;
  stocks: StockData[];
  totalChecked: number;
  dataSource: string;
  downloadUrls: {
    csv: string;
    excel: string;
  };
}
```

#### 3.2 数据服务层
```typescript
// src/services/dataService.ts
class DataService {
  // 统一的数据获取接口
  async runScreener(
    screenerId: string, 
    date: string, 
    useRealtime: boolean = false
  ): Promise<ScreenerRunResult> {
    const endpoint = useRealtime 
      ? `/screener/${screenerId}/realtime-run`
      : `/screeners/${screenerId}/run`;
    
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date })
    });
    
    const data = await response.json();
    
    // 统一转换响应格式
    return this.normalizeRunResult(data, useRealtime);
  }
  
  private normalizeRunResult(rawData: any, isRealtime: boolean): ScreenerRunResult {
    // 标准化不同数据源的返回格式
    return {
      screenerId: rawData.screener || rawData.screener_id,
      screenerName: rawData.screener_name || '',
      runDate: rawData.date || rawData.run_date,
      isRealtime,
      stocks: this.normalizeStocks(rawData.results || rawData.stocks),
      totalChecked: rawData.total_checked || rawData.count,
      dataSource: isRealtime ? 'ifind' : 'baostock',
      downloadUrls: {
        csv: rawData.file_paths?.csv || '',
        excel: rawData.file_paths?.excel || ''
      }
    };
  }
}
```

---

### 阶段四：环境稳定性 (下周)

#### 4.1 统一配置管理
```yaml
# config/application.yaml
environment: production

data_sources:
  primary: baostock
  fallback: ifind
  
  baostock:
    db_path: data/stock_data.db
    update_time: "16:00"
    
  ifind:
    base_url: https://quantapi.51ifind.com/api/v1
    refresh_token: ${IFIND_TOKEN}
    expires_at: "2026-04-02"
    
dashboard:
  flask_port: 5004
  ngrok_domain: chariest-nancy-nonincidentally.ngrok-free.dev
  password: ${DASHBOARD_PASSWORD}
  
monitoring:
  check_interval: 60
  max_retries: 3
```

#### 4.2 监控脚本修复
```python
# scripts/monitor_dashboard.py
class DashboardMonitor:
    """改进的监控脚本"""
    
    def __init__(self):
        self.config = load_config()
        self.flask_env = {
            'DASHBOARD_PASSWORD': self.config.dashboard.password,
            'FLASK_PORT': str(self.config.dashboard.flask_port)
        }
    
    def start_flask(self):
        """启动 Flask 时确保环境变量"""
        env = os.environ.copy()
        env.update(self.flask_env)
        subprocess.Popen(
            ['python3', 'app.py', '--port', env['FLASK_PORT']],
            env=env,
            cwd='dashboard'
        )
```

---

## 📝 实施计划

### 本周任务（由 Agent 团队执行）

| Agent | 任务 | 优先级 | 预估时间 |
|-------|------|--------|----------|
| **Backend Architect** | 创建数据抽象层 (DataSource 基类) | P0 | 4h |
| **Backend Architect** | 重构 Baostock 数据源实现 | P0 | 3h |
| **Backend Architect** | 重构 iFind 数据源实现 | P0 | 3h |
| **Backend Architect** | 统一 API 响应格式 | P1 | 2h |
| **Frontend Developer** | 创建前端数据服务层 | P1 | 4h |
| **DevOps Automator** | 修复监控脚本环境变量问题 | P0 | 1h |
| **SRE** | 建立配置管理系统 | P1 | 2h |

### 下周任务
- 前端组件重构
- 自动化测试编写
- 文档完善
- 性能优化

---

## 🎯 成功标准

1. **数据源切换**: 修改一行配置即可切换主数据源
2. **接口一致性**: 所有 API 返回统一格式，前端无需判断数据源
3. **错误处理**: 自动降级，用户无感知
4. **代码可测试**: 新增自动化测试，覆盖率 > 60%
5. **文档完整**: 每个模块有接口文档和使用说明

---

## 💡 建议的执行顺序

1. **立即** (今晚): 
   - 修复监控脚本的环境变量问题（保证稳定性）
   - 制定详细的代码规范文档

2. **明天**:
   - Backend Architect 开始数据抽象层
   - Frontend Developer 开始前端服务层

3. **本周末**:
   - 完成核心重构
   - 集成测试

4. **下周一**:
   - 部署到生产环境
   - 观察稳定性

你觉得这个方案如何？需要我立即开始哪一部分？