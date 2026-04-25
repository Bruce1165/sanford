# 项目配置参数

## 核心配置

### 端口配置
- **Flask 后端端口**: `8765`
  - 启动命令: `cd backend && python3 app.py --port 8765`
  - 访问地址: `http://localhost:8765` (直接访问，不需要3000)
  - Flask同时提供API和前端静态文件

- **Vite 前端端口**: `3000` (仅开发时使用)
  - 启动命令: `cd frontend && npm run dev`
  - 用途：开发时实时热更新（修改代码后自动刷新）
  - 平时不需要启动

- **Cpolar 隧道**: 用于外部访问（配置在 `~/.cpolar/cpolar.yml`）

### 认证配置
- **环境变量**: `DASHBOARD_PASSWORD`
- **当前密码**: `NeoTrade123`
- **设置命令**: `export DASHBOARD_PASSWORD="NeoTrade123"`
- **本地访问**: 跳过认证（127.0.0.1, localhost, 192.168.x.x, 10.x.x.x, 172.16-31.x.x）
- **外部访问**: 需要 Basic Auth 认证

## 数据库

### 数据库路径
- **主数据库**: `data/stock_data.db` (股票数据)
- **Dashboard数据库**: `data/dashboard.db` (筛选器运行记录、配置历史)

### 重要表结构

#### stock_data.db
- `stocks` - 股票基本信息
- `daily_prices` - 每日价格数据

#### dashboard.db
- `screeners` - 筛选器定义
- `screener_runs` - 筛选器运行记录
- `screener_results` - 筛选器结果
- `screener_configs` - 筛选器配置（新增）
- `screener_config_history` - 配置版本历史（新增）
- `strategy_backtest_results` - 战法回测结果

## 筛选器配置

### 配置文件路径
- **配置目录**: `config/screeners/`
- **文件格式**: JSON
- **文件命名**: `{screener_name}.json`

### 14个筛选器列表
1. `er_ban_hui_tiao` - A-二板回调
2. `jin_feng_huang` - B2-涨停金凤凰
3. `yin_feng_huang` - C1-涨停银凤凰
4. `shi_pan_xian` - C2-涨停试盘线
5. `zhang_ting_bei_liang_yin` - B1-放量阴拉涨停
6. `shuang_shou_ban` - 双首板
7. `ashare_21` - A股2.1综合选股
8. `coffee_cup` - 杯柄形态
9. `breakout_20day` - 20日突破
10. `breakout_main` - 主升浪突破
11. `daily_hot_cold` - 每日冷热榜
12. `ascending_triangle` - 上升三角形
13. `double_bottom` - 双底形态
14. `high_tight_flag` - 高旗杆形态

### 有参数的筛选器
- `er_ban_hui_tiao`: LIMIT_DAYS (默认14, 范围1-60)
- `jin_feng_huang`: LIMIT_DAYS (默认14, 范围1-60)
- `yin_feng_huang`: LIMIT_DAYS (默认14, 范围1-60)
- `zhang_ting_bei_liang_yin`: LIMIT_DAYS (默认14, 范围1-60)
- `ashare_21`: LOOKBACK_DAYS (默认20, 范围5-60), MIN_SCORE (默认60, 范围0-100)

## API 端点

### 筛选器相关
- `GET /api/screeners` - 获取所有筛选器
- `GET /api/screeners/<name>` - 获取筛选器详情
- `POST /api/screeners/<name>/run` - 运行筛选器
- `GET /api/results` - 获取筛选器结果
- `GET /api/runs` - 获取运行记录

### 配置管理（新增）
- `GET /api/screeners/<name>/config` - 获取配置
- `PUT /api/screeners/<name>/config` - 更新配置
- `GET /api/screeners/<name>/history` - 获取版本历史
- `POST /api/screeners/<name>/rollback` - 回滚配置

### 其他
- `GET /api/health` - 健康检查（无需认证）
- `GET /api/monitor/screeners` - 监控数据

## 环境变量

### 必需变量
- `DASHBOARD_PASSWORD` - Dashboard访问密码

### 可选变量
- `WORKSPACE_ROOT` - 项目根目录（自动检测）

## 启动流程

### 完整启动流程
```bash
# 1. 设置环境变量
export DASHBOARD_PASSWORD="NeoTrade123"

# 2. 启动Flask后端
cd backend
python3 app.py --port 8765

# 3. 启动Vite前端（新终端）
cd frontend
npm run dev
```

### 快速启动（开发模式）
```bash
# 使用快捷脚本（如果有）
./scripts/start_dev.sh
```

## 目录结构

```
NeoTrade2/
├── backend/              # Flask 后端
│   ├── app.py          # 主应用 (端口 8765)
│   ├── models.py       # 数据库模型
│   ├── config_loader.py # 配置加载器
│   ├── validators.py    # 参数验证器
│   └── docstring_updater.py # Docstring更新器
├── frontend/            # React 前端
│   ├── src/
│   │   ├── api/       # API 客户端
│   │   ├── components/ # React 组件
│   │   └── pages/     # 页面组件
│   ├── vite.config.ts # Vite 配置 (代理到 8765)
│   └── package.json
├── screeners/          # 筛选器模块
│   ├── base_screener.py
│   └── *_screener.py  # 各个筛选器实现
├── config/            # 配置文件
│   └── screeners/     # 筛选器配置 (JSON)
├── data/              # 数据文件
│   ├── stock_data.db  # 股票数据
│   └── dashboard.db   # Dashboard 数据
└── scripts/           # 脚本工具
```

## 常用命令

### 开发
```bash
# 启动后端
cd backend && python3 app.py --port 8765

# 启动前端
cd frontend && npm run dev

# 下载当日数据
python3 scripts/fetcher_baostock.py --loop

# 运行所有筛选器
python3 scripts/run_all_screeners.py --date 2026-04-04
```

### 测试
```bash
# 快速验证
python3 backend/quick_verification.py

# 测试配置加载
python3 backend/test_config_loading.py

# 测试所有配置文件
python3 backend/test_load_all_configs.py
```

### 数据库
```bash
# 检查数据库完整性
sqlite3 data/dashboard.db "PRAGMA integrity_check;"

# 查看配置历史
sqlite3 data/dashboard.db "SELECT * FROM screener_config_history WHERE screener_name='er_ban_hui_tiao' ORDER BY created_at DESC LIMIT 5;"
```

## 故障排查

### 登录弹窗问题
1. 确认端口：Flask应该运行在8765，前端代理配置正确
2. 重启服务：停止所有Python和Vite进程，重新启动
3. 清除浏览器缓存：使用无痕模式或强制刷新
4. 检查IP识别：查看Flask日志中的 `[AUTH]` 输出

### API请求失败
1. 检查Flask是否运行：`lsof -i :8765`
2. 检查Vite代理配置：`frontend/vite.config.ts`
3. 查看浏览器Network面板的错误信息
4. 检查CORS配置

### 数据库问题
1. 检查数据库文件是否存在
2. 运行完整性检查
3. 检查文件权限

## 重要提醒

1. **每次修改代码后必须重启服务**才能生效
2. **外部访问需要密码**：`NeoTrade123`
3. **本地开发不需要密码**（localhost访问）
4. **配置文件修改会自动备份到历史表**
5. **端口冲突**：如果8765被占用，使用其他端口但要同步更新vite.config.ts

## 更新日志

### 2026-04-04
- 添加筛选器配置管理系统
- 新增4个API端点用于配置管理
- 修改认证逻辑，本地访问无需密码
- 创建14个筛选器配置文件
- 端口标准化为8765（Flask）和3000（前端）
