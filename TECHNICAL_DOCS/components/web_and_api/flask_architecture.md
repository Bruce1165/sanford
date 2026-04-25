# Flask 后端架构文档

> NeoTrade2 Flask 后端的技术架构、API 设计和模块说明

## 📋 目录

- [系统概览](#系统概览)
- [目录结构](#目录结构)
- [核心模块](#核心模块)
- [路由设计](#路由设计)
- [数据模型](#数据模型)
- [认证机制](#认证机制)
- [相关文档](#相关文档)

---

## 系统概览

### 技术栈
- **Web 框架**: Flask 3.0
- **数据库**: SQLite 3 (dashboard.db, stock_data.db)
- **Python**: 3.11
- **认证**: HTTP Basic Auth
- **前端**: React + Vite (Flask 静态服务)

### 运行模式
- **开发模式**: 直接运行 `python3 app.py --port 8765`
- **生产模式**: Launchd 系统 service
- **日志输出**: `logs/flask.stdout.log` 和 `logs/flask.stderr.log`

### 配置参考
- **认证配置**: 请参考 [02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)
- **端口配置**: 请参考 [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)
- **API 端点**: 请参考 [08_API_REFERENCE.md](08_API_REFERENCE.md)

---

## 目录结构

```
backend/
├── app.py                 # Flask 主应用
├── models.py              # SQLAlchemy 数据模型
├── screeners.py            # 筛选器发现和执行
├── config_loader.py       # 配置加载和验证
├── validators.py           # 请求验证
├── docstring_updater.py    # 文档字符串更新（可选）
├── excel_upload.py         # Excel 文件上传
├── strategy_management.py   # 策略管理
└── logs/                  # 日志目录
```

---

## 核心模块

### app.py
Flask 主应用，包含：
- 路由定义
- 认证中间件
- 错误处理
- 响应格式化

关键函数：
- `get_screener_schema()` - 动态加载筛选器参数 Schema
- `update_screener_config_endpoint()` - 更新筛选器配置
- `get_screener_runs()` - 获取筛选器运行记录

### models.py
SQLAlchemy 数据模型：
- `Screener` - 筛选器定义
- `ScreenerRun` - 筛选器执行记录
- `ScreenerResult` - 筛选结果
- `ScreenerConfig` - 筛选器配置
- `ScreenerConfigVersion` - 配置版本历史

### screeners.py
筛选器发现和执行：
- `register_discovered_screeners()` - 注册所有筛选器
- `run_screener_subprocess()` - 子进程执行筛选器
- `get_stock_data_for_chart()` - 获取图表数据

### config_loader.py
配置加载和验证：
- `ConfigLoader.load_config()` - 加载配置（优先数据库，回退文件）
- `ConfigLoader.save_config()` - 保存配置（数据库 + 文件）
- `ConfigLoader.validate_parameters()` - 参数验证

---

## 路由设计

```
/                          → catch_all()       → serve index.html (React Router)
/api/screeners          → get_all_screeners()
/api/screeners/<name>     → get_screener(name)
/api/screeners/<name>/run  → run_screener(name)
/api/results             → get_screener_results(...)  # requires screener + date
/api/trading-day         → is_trading_day(...)
/api/stock/<code>/chart → get_stock_data_for_chart(...)
/api/screeners/<name>/config → get/update_screener_config(...)
/api/health              → health_check()
/assets/<path>            → serve_assets()
```

### 筛选器运行与日期语义（严格策略）

- **requested_date**：调用方传入的日期（YYYY-MM-DD）
- **effective_trade_date**：实际交易日（必须是交易日；严格模式下与 requested_date 相同）
- `GET /api/trading-day?date=YYYY-MM-DD`
  - 返回 `is_trading_day` 与 `recent_trading_day`（基于 `daily_prices`：`MAX(trade_date) <= requested_date`）。
- `POST /api/screeners/<name>/run`
  - 若 `requested_date` 非交易日：返回 `400`，body 含 `{ error, requested_date, effective_trade_date }`。
  - 若为交易日：正常运行，响应中包含 `{ requested_date, effective_trade_date }`。
- `GET /api/results?screener=<name>&date=YYYY-MM-DD`
  - `screener` 必填；`date` 必须为交易日。
  - 非交易日返回 `400`（同样包含 `{ error, requested_date, effective_trade_date }`）。

**完整 API 文档请参考**: [08_API_REFERENCE.md](08_API_REFERENCE.md)

---

## 数据模型

### ScreenerConfig
```python
{
  "screener_name": "breakout_20day",
  "display_name": "20日突破",
  "description": "...",
  "category": "突破信号",
  "current_version": "v1.1",
  "updated_at": "2026-04-09T13:00:00",
  "config_json": {
    "parameters": { ... }
  }
}
```

### ScreenerConfigVersion
```python
{
  "version": "v1.1",
  "config_json": { ... },
  "change_summary": "...",
  "changed_by": "admin",
  "created_at": "..."
}
```

---

## 认证机制

### HTTP Basic Auth
- **环境变量**: `DASHBOARD_PASSWORD`
- **配置位置**: 请参考 [02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)
- **认证方式**: 所有请求都需要密码验证
- **浏览器行为**: 原生登录窗口，一次会话内记住凭据

### 检查逻辑
```python
def check_auth(username, password):
    """验证密码（只验证密码，用户名随意）"""
    return password == DASHBOARD_PASSWORD
```

---

## 相关文档

- **[02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)** - 系统配置详解
- **[08_API_REFERENCE.md](08_API_REFERENCE.md)** - API 端点完整文档
- **[13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)** - 服务管理命令
- **[01_START_SERVER.md](01_START_SERVER.md)** - 启动服务说明

---

**最后更新**: 2026-04-10
