# 系统配置记录

## 📋 目录

- [认证配置](#认证配置)
- [服务架构](#服务架构)
- [目录结构](#目录结构)
- [数据库](#数据库)
- [筛选器列表](#筛选器列表)
- [文件路径](#文件路径)
- [相关文档](#相关文档)

---

## 认证配置

### 密码配置
- **当前密码**: `NeoTrade123`
- **环境变量**: `DASHBOARD_PASSWORD`
- **配置文件**:
  - `/Users/mac/NeoTrade2/config/.env`
  - `~/Library/LaunchAgents/com.neotrade2.flask.plist`

### 认证状态（2026-04-10）
- **所有请求都需要密码**（包括本地访问）
- **认证方式**: HTTP Basic Auth
- **认证层级**: 单层认证（仅 Flask，Cpolar 不添加额外认证）
- **浏览器行为**: 弹出原生登录窗口，一次会话内记住凭据
- **用户名**: 任意值（仅验证密码）

---

## 服务架构

### 当前方式（2026-04-10）
- **系统服务**：通过 macOS Launchd 自动启动
- **Flask 服务**：`com.neotrade2.flask`
- **Cpolar 服务**：`com.neotrade.cpolar`
- **自动启动**：登录 macOS 时自动启动
- **KeepAlive**: 服务异常退出后自动重启

### 配置参考
- **端口配置**：请参考 [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)
- **服务管理命令**：请参考 [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)

---

## 目录结构

```
/Users/mac/NeoTrade2/
├── backend/              # Flask 后端
│   ├── app.py          # 主应用
│   ├── models.py       # 数据库模型
│   ├── config_loader.py # 配置加载器
│   ├── validators.py    # 参数验证器
│   └── docstring_updater.py # Docstring更新器
├── frontend/            # React 前端
│   ├── dist/           # 生产构建（已构建）
│   └── src/            # 源代码
├── screeners/          # 筛选器模块
│   ├── base_screener.py
│   └── *_screener.py  # 各个筛选器
├── config/            # 配置文件
│   └── screeners/     # 筛选器配置（14个JSON文件）
├── data/              # 数据文件
│   ├── stock_data.db  # 股票数据
│   └── dashboard.db   # Dashboard数据
└── scripts/           # 工具脚本
```

---

## 数据库

### stock_data.db
- **路径**: `/Users/mac/NeoTrade2/data/stock_data.db`
- **表**: `stocks`, `daily_prices`
- **用途**: 存储股票基础数据和每日价格

### dashboard.db
- **路径**: `/Users/mac/NeoTrade2/data/dashboard.db`
- **表**:
  - `screeners` - 筛选器定义
  - `screener_runs` - 运行记录
  - `screener_results` - 筛选结果
  - `screener_configs` - 配置
  - `screener_config_history` - 配置历史
  - `strategy_backtest_results` - 策略回测结果

---

## 筛选器列表

1. `er_ban_hui_tiao` - A股二板回调
2. `jin_feng_huang` - B2涨停金凤凰
3. `yin_feng_huang` - C1涨停银凤凰
4. `shi_pan_xian` - C2涨停试盘线
5. `zhang_ting_bei_liang_yin` - B1放量阴拉涨停
6. `shuang_shou_ban` - 双首板
7. `ashare_21` - A股2.1综合选股
8. `coffee_cup` - 咖啡杯形态
9. `breakout_20day` - 20日突破
10. `breakout_main` - 主升浪突破
11. `daily_hot_cold` - 每日冷热榜
12. `ascending_triangle` - 上升三角形
13. `double_bottom` - 双底形态
14. `high_tight_flag` - 高旗杆形态

---

## 文件路径

### 配置文件
- 筛选器配置: `/Users/mac/NeoTrade2/config/screeners/*.json`

### 数据文件
- 股票数据: `/Users/mac/NeoTrade2/data/stock_data.db`
- Dashboard数据: `/Users/mac/NeoTrade2/data/dashboard.db`

---

## 相关文档

- **[01_START_SERVER.md](01_START_SERVER.md)** - 启动服务说明
- **[13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)** - 服务管理完整命令
- **[08_API_REFERENCE.md](08_API_REFERENCE.md)** - API 端点完整文档
- **[06_OPERATIONS.md](06_OPERATIONS.md)** - 运维和数据库维护

---

**最后更新**: 2026-04-10
