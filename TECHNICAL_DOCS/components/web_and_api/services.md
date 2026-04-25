# Flask 和 Cpolar 服务说明

**Date**: 2026-04-10  
**Version**: 1.0  
**Purpose**: 解释 NeoTrade2 项目的 Flask 后端和 Cpolar 隧道服务如何协同工作

---

## 📋 目录

- [服务架构](#服务架构)
- [Flask 服务](#flask-服务)
- [Cpolar 服务](#cpolar-服务)
- [工作流程](#工作流程)
- [管理命令](#管理命令)
- [常见问题](#常见问题)

---

## 服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户浏览器                              │
│                         ↓                                  │
│                  访问 https://neotrade.vip.cpolar.cn/           │
│                                                              │
│                         ┌────────────────────────┴──────────────┐     │
│                         │                                   │     │
│                  ┌─────┴─────┐        │    ┌───┴───┐     │
│         ┌────┴──┐  │           │    │         │     │     │
│         │ Cpolar   │           │    │   Flask  │     │     │     │
│  HTTPS  隧道   │           │    │  后端 API │     │     │     │
│         │           │           │    │         │     │     │     │
│      ┌───┴──┐    │           │    │         │     │     │     │
│  ┌─┴───────┐  │           │    │         │     │     │     │     │
│  │ 本地 8765  │  │           │    │         │     │     │     │     │
│  │ Flask 服务   │  │           │    │         │     │     │     │     │
│  └───┴──────┘  │           │    │         │     │     │     │     │     │
│      转发请求到 8765  │           │    │         │     │     │     │     │     │
└─────────────────────────────────────────────────────────────┘
```

### 数据流向

```
用户浏览器
  ↓ HTTPS 请求
Cpolar 隧道
  ↓ 转发到本地
Flask 后端 (8765)
  ↓ 提供前端静态文件 + API
前端 React 应用
```

---

## Flask 服务

### 服务信息

- **服务名**: `com.neotrade2.flask`
- **进程文件**: `~/Library/LaunchAgents/com.neotrade2.flask.plist`
- **端口**: 8765
- **状态**: 运行时通过 `launchctl list` 可见
- **日志位置**:
  - `/Users/mac/NeoTrade2/logs/flask.stdout.log`
  - `/Users/mac/NeoTrade2/logs/flask.stderr.log`
  - `/Users/mac/NeoTrade2/logs/dashboard.log`

### 主要功能

1. **提供 REST API**
   - 筛选器管理 (`/api/screeners`)
   - 筛选结果 (`/api/results`)
   - 配置管理 (`/api/screeners/<name>/config`)
   - 股票数据 (`/api/stock/<code>/chart`)
   - 监控数据 (`/api/monitor/screeners`)

2. **提供前端静态文件**
   - 路径: `frontend/dist/`
   - 包含: `index.html`, `assets/` (JS/CSS)
   - 缓存策略:
     - 带哈希的资源: 缓存 1 年
     - 不带哈希的资源: 无缓存

3. **认证机制**
   - 方式: HTTP Basic Auth
   - 密码: 通过 `DASHBOARD_PASSWORD` 环境变量配置
   - **详细配置请参考**: [02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)
   - Launchd 配置: `~/Library/LaunchAgents/com.neotrade2.flask.plist`
   - **认证层级**: 单层认证（仅 Flask，Cpolar 不添加额外认证）

4. **CORS 配置**
   ```python
   CORS_ORIGINS = [
       'http://localhost:5173',    # Vite dev server
       'http://localhost:3000',    # Alternative dev server
       'http://127.0.0.1:5173',
       'http://127.0.0.1:3000',
       'https://neotrade.cpolar.cn',  # Cpolar HTTPS
       'https://neiltrade.cloud',      # Cpolar HTTPS (仅 HTTPS!)
   ]
   ```
   **重要**: 不再包含 `http://neotrade.cpolar.cn` 和 `http://neiltrade.cloud`，避免混合内容问题

### 配置文件位置

- **主应用**: `/Users/mac/NeoTrade2/backend/app.py`
- **环境变量**: `/Users/mac/NeoTrade2/config/.env`
- **数据库**: `/Users/mac/NeoTrade2/data/dashboard.db`

### 调试配置

以下调试日志已添加到 `app.py`:
```python
print(f"[DEBUG] Loading .env from: {env_file}")
print(f"[DEBUG] DASHBOARD_PASSWORD loaded: {DASHBOARD_PASSWORD[:10]}...")
print(f"[DEBUG] CORS Origins (NO HTTP CPOLAR): {CORS_ORIGINS}")
```

查看实时日志:
```bash
tail -f /Users/mac/NeoTrade2/logs/flask.stdout.log
```

---

## Cpolar 服务

### 服务信息

- **服务名**: `com.neotrade.cpolar`
- **进程文件**: `~/Library/LaunchAgents/com.neotrade.cpolar.plist`
- **外部访问**: `https://neotrade.vip.cpolar.cn`
- **状态**: 需要通过 `launchctl` 查看
- **配置文件**: `~/.cpolar/cpolar.yml`

### 主要功能

1. **HTTPS 隧道**
   - 将外部 HTTPS 请求转发到本地服务
   - 子域名: `neotrade.vip.cpolar.cn`
   - 目标地址: 本地服务的端口 8765

2. **自动注入资源** (免费版特性)
   - Cpolar 可能注入自己的 CSS/字体文件
   - 问题: 使用 `http://static.cpolar.com/css/fonts/...` 而主页面是 HTTPS
   - 结果: 浏览器阻止不安全内容（混合内容错误）
   - **注意**: 这是 Cpolar 免费版的限制，无法通过代码修复

### Cpolar 配置

检查 Cpolar 配置:
```bash
cat ~/.cpolar/cpolar.yml
```

检查 Cpolar 服务状态:
```bash
launchctl list | grep -i cpolar
```

---

## 工作流程

### 正常工作流程

1. **Flask 服务自动启动**
   - 登录 macOS 时通过 launchd 自动启动
   - 监听端口 8765
   - 提供前端和 API

2. **Cpolar 隧道正常运行**
   - 转发 `https://neotrade.vip.cpolar.cn` 到本地 8765
   - 用户通过 Cpolar URL 访问 Dashboard

3. **用户访问 Dashboard**
   - 浏览器请求: `https://neotrade.vip.cpolar.cn/?tab=screeners`
   - Cpolar 转发到 Flask: `http://localhost:8765/?tab=screeners`
   - Flask 返回前端页面和 API 数据

### 故障场景

#### 场景 1: Cpolar 服务未运行

**症状**:
- 访问 `https://neotrade.vip.cpolar.cn/` 得到 404 错误
- 或看到 Cpolar 的 404 错误页面

**解决方案**:
```bash
# 手动加载并启动 Cpolar 服务
launchctl load ~/Library/LaunchAgents/com.neotrade.cpolar.plist
launchctl start com.neotrade.cpolar

# 验证运行状态
launchctl list | grep -i cpolar
```

#### 场景 2: Flask 服务未运行

**症状**:
- 访问 `https://neotrade.vip.cpolar.cn/` 得到连接错误
- API 请求失败

**解决方案**:
```bash
# 重启 Flask 服务
launchctl kickstart -k gui/$(id -u)/com.neotrade2.flask

# 查看日志确认启动
tail -20 /Users/mac/NeoTrade2/logs/flask.stdout.log
```

#### 场景 3: 混合内容警告

**症状**:
```
[Warning] [blocked] The page at https://neotrade.vip.cpolar.cn/... requested 
insecure content from http://static.cpolar.com/css/fonts/...
```

**原因**:
- Cpolar 隧道是 HTTPS
- 但 Cpolar 注入的 CSS 文件使用 HTTP
- 浏览器阻止不安全的 HTTP 资源

**说明**:
- 这是 Cpolar 免费版的功能
- 不影响 Dashboard 功能使用
- Flask 代码已配置正确（仅允许 HTTPS 源）
- 无法通过代码修复

**临时解决方案**:
- 忽略警告（Dashboard 仍然正常工作）
- 升级到 Cpolar 付费版以禁用资源注入

---

## 管理命令

### 启动服务

#### 同时启动两个服务（开发时需要）
```bash
# 终端 1: 启动 Flask
cd /Users/mac/NeoTrade2
DASHBOARD_PASSWORD=NeoTrade123 python3 backend/app.py --port 8765

# 终端 2: 启动 Cpolar 隧道
cpolar start
```

### 重启服务

#### 重启 Flask 服务
```bash
launchctl kickstart -k gui/$(id -u)/com.neotrade2.flask
```

#### 重启 Cpolar 服务
```bash
# 方法 1: 如果服务已加载
launchctl restart com.neotrade.cpolar

# 方法 2: 重新加载并启动
launchctl load ~/Library/LaunchAgents/com.neotrade.cpolar.plist
launchctl start com.neotrade.cpolar
```

### 停止服务

#### 停止 Flask 服务
```bash
launchctl stop com.neotrade2.flask
```

#### 停止 Cpolar 服务
```bash
launchctl stop com.neotrade.cpolar
```

### 查看服务状态

```bash
# 查看 Flask 服务
launchctl list | grep -i flask

# 查看 Cpolar 服务
launchctl list | grep -i cpolar

# 查看所有服务
launchctl list
```

### 查看日志

#### Flask 实时日志
```bash
# 标准输出日志
tail -f /Users/mac/NeoTrade2/logs/flask.stdout.log

# 错误日志
tail -f /Users/mac/NeoTrade2/logs/flask.stderr.log

# Dashboard 日志
tail -f /Users/mac/NeoTrade2/logs/dashboard.log
```

### 查看端口占用

```bash
# 查看 8765 端口是否被占用
lsof -i :8765

# 查看端口对应的进程
lsof -i :8765 -P
```

---

## 常见问题

### Q1: 为什么 Cpolar 隧道无法建立，显示 "没有 authtoken"？

**症状**:
- Cpolar 日志显示：`启动时没有authtoken`
- 无法建立隧道
- 外部 URL 无法访问

**原因**:
- `~/.cpolar/cpolar.yml` 配置文件为空或 authtoken 丢失
- Cpolar 无法连接到认证服务器

**解决方案**:
```bash
# 1. 获取 authtoken（从 Cpolar Dashboard）
# 访问 https://dashboard.cpolar.cn/login

# 2. 配置 authtoken
cpolar authtoken <你的authtoken>

# 3. 验证已保存
cat ~/.cpolar/cpolar.yml

# 4. 重启 Cpolar 服务
launchctl stop com.neotrade.cpolar
launchctl unload ~/Library/LaunchAgents/com.neotrade.cpolar.plist
launchctl load ~/Library/LaunchAgents/com.neotrade.cpolar.plist

# 5. 验证隧道已建立
tail -5 /Users/mac/neotrade_cpolar.log | grep "Tunnel established"
```

### Q2: 为什么登录弹窗重复出现，无法登录？

**症状**:
- 访问外部 URL 时连续弹出两个登录框
- Flask 和 Cpolar 都要求认证
- 两个系统的用户名密码不一致

**原因**:
1. **双重认证冲突**:
   - Flask Basic Auth（通过 Launchd 配置）
   - Cpolar HTTP Auth（通过启动脚本 `--httpauth` 参数）
   - 两个认证层使用不同的密码

2. **Flask 密码格式错误**:
   - Launchd 配置中密码包含用户名（如 `admin/bruce2024`）
   - Flask 的 Basic Auth 验证是 `password == DASHBOARD_PASSWORD`
   - 应该是纯密码（如 `NeoTrade123`）

**解决方案**:
```bash
# 1. 移除 Cpolar HTTP 认证
# 编辑 /Users/mac/start_cpolar_auth.sh，删除 --httpauth 参数
/usr/local/bin/cpolar http 8765 --subdomain=neotrade --region=cn_vip ...

# 2. 修正 Flask 密码配置
# 编辑 ~/Library/LaunchAgents/com.neotrade2.flask.plist
<key>DASHBOARD_PASSWORD</key>
<string>NeoTrade123</string>  <!-- 纯密码，不要包含用户名 -->

# 3. 重启两个服务
launchctl stop com.neotrade.cpolar
launchctl stop com.neotrade2.flask
launchctl unload ~/Library/LaunchAgents/com.neotrade.cpolar.plist
launchctl unload ~/Library/LaunchAgents/com.neotrade2.flask.plist
launchctl load ~/Library/LaunchAgents/com.neotrade.cpolar.plist
launchctl load ~/Library/LaunchAgents/com.neotrade2.flask.plist

# 4. 验证服务正常
curl -s -u "any:NeoTrade123" -k https://neotrade.vip.cpolar.cn/ | grep "NEO Dashboard"
```

### Q3: 为什么访问 Cpolar URL 时显示 404？

**A1**: Cpolar 服务未运行

**检查和修复**:
```bash
# 1. 检查 Cpolar 服务状态
launchctl list | grep -i cpolar

# 2. 如果没有显示，手动加载并启动
launchctl load ~/Library/LaunchAgents/com.neotrade.cpolar.plist
launchctl start com.neotrade.cpolar

# 3. 验证服务已启动
launchctl list | grep -i cpolar

# 4. 等待几秒后测试访问
curl -I https://neotrade.vip.cpolar.cn/
```

**A2**: Flask 服务未运行

**检查和修复**:
```bash
# 1. 检查 Flask 服务状态
launchctl list | grep -i flask

# 2. 如果没有显示，重启服务
launchctl kickstart -k gui/$(id -u)/com.neotrade2.flask

# 3. 查看日志确认启动成功
tail -20 /Users/mac/NeoTrade2/logs/flask.stdout.log

# 4. 测试本地访问
curl -u admin:NeoTrade123 http://localhost:8765/
```

### Q2: 看到混合内容警告，怎么解决？

**症状**:
```
[Warning] [blocked] The page at https://neotrade.vip.cpolar.cn/... requested 
insecure content from http://static.cpolar.com/css/fonts/...
```

**原因**:
- Cpolar 免费版注入自己的 CSS/字体文件
- 这些文件使用 HTTP 协议，但主页面通过 HTTPS 加载

**重要说明**:
1. **这不是代码问题** - Flask 的 CORS 配置已经是正确的
2. **不影响功能** - Dashboard 仍然正常工作
3. **无法通过代码修复** - 这是 Cpolar 免费版的特性

**解决方案**:
- **临时**: 忽略警告，不影响使用
- **永久**: 升级到 Cpolar 付费版并禁用资源注入功能

### Q3: 修改 Flask 代码后，怎么让修改生效？

**步骤**:
```bash
# 1. 修改 Flask 代码（已完成 CORS 配置）
# 2. 重启 Flask 服务以应用新配置
launchctl kickstart -k gui/$(id -u)/com.neotrade2.flask

# 3. 查看日志确认新配置生效
tail -20 /Users/mac/NeoTrade2/logs/flask.stdout.log

# 应该看到:
# [DEBUG] CORS Origins (NO HTTP CPOLAR): ['http://localhost:5173', ...]
```

### Q4: 如何验证两个服务都在运行？

**命令**:
```bash
# 完整状态检查
echo "=== Flask 服务 ==="
launchctl list | grep -i flask
echo ""
echo "=== Cpolar 服务 ==="
launchctl list | grep -i cpolar
echo ""
echo "=== 端口检查 ==="
lsof -i :8765 -P

echo "=== 最近 Flask 日志 ==="
tail -5 /Users/mac/NeoTrade2/logs/flask.stdout.log
```

**期望输出**:
```
=== Flask 服务 ===
49149	0	com.neotrade2.flask

=== Cpolar 服务 ===
55326	0	com.neotrade.cpolar

=== 端口检查 ===
*:*:8765
```

---

## 技术架构细节

### Flask 路由设计

```
/                          → catch_all()       → serve index.html (React Router)
/api/screeners          → get_all_screeners()
/api/screeners/<name>     → get_screener(name)
/api/screeners/<name>/run  → run_screener(name)
/api/results             → get_results(...)
/api/stock/<code>/chart → get_stock_data_for_chart(...)
/api/screeners/<name>/config → get/update_screener_config(...)
/api/health              → health_check()
/assets/<path>            → serve_assets()
```

### 静态文件服务

```python
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    response = send_from_directory(DASHBOARD_DIR.parent / 'frontend/dist/assets', filename)
    
    # 带哈希的资源（如 index-bE3lrhQ1.js）：缓存 1 年
    if '.' in filename and filename.split('.')[-2] and len(filename.split('.')[-2]) > 8:
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    # 不带哈希的资源：无缓存
    else:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    
    return response
```

### 认证中间件

```python
def authenticate():
    """返回 401 响应要求认证"""
    resp = Response(
        '请输入密码访问 Dashboard',
        401,
        {'WWW-Authenticate': 'Basic realm="NeoTrade Dashboard"'}
    )
    return resp

@app.before_request
def before_request():
    """为所有路由添加认证（健康检查除外）"""
    if request.path == '/api/health':
        return
    
    auth = request.authorization
    if not auth:
        return authenticate()
    
    username, password = auth
    if not check_auth(username, password):
        return authenticate()
```

---

## 防护和安全

### 密码管理

- ✅ **不要在代码中硬编码密码**
- 使用环境变量 `DASHBOARD_PASSWORD`
- 从 `/Users/mac/NeoTrade2/config/.env` 读取

### Authtoken 管理

- ✅ **定期备份 Cpolar 配置**
  ```bash
  cp ~/.cpolar/cpolar.yml ~/.cpolar/cpolar.yml.bak
  ```

- ✅ **配置一致性检查**
  确保以下位置的密码一致：
  - `config/.env` - `DASHBOARD_PASSWORD`
  - `~/Library/LaunchAgents/com.neotrade2.flask.plist` - EnvironmentVariables

- ✅ **避免双重认证**
  - Flask Basic Auth 提供应用层保护
  - Cpolar 只做隧道转发，不需要额外认证
  - 保持单一认证层，提升用户体验

### CORS 安全

- ✅ **仅允许 HTTPS 源用于外部 Cpolar 域道**
- 已移除 `http://neotrade.cpolar.cn` 和 `http://neiltrade.cloud`
- 仅保留 HTTPS 版本

### 日志和监控

- ✅ **完整的调试日志已添加**
- 启动时打印 CORS 配置
- 所有请求都会记录访问日志

### 输入验证

- ⚠️ **需要添加**：API 参数的输入验证（当前部分实现）

---

## 更新历史

### 2026-04-10
- 添加 Flask 和 Cpolar 服务完整文档
- 修复 CORS 配置以避免混合内容警告
- 添加调试日志到 Flask 服务
- 添加常见问题排查指南
- 更新认证密码为 `NeoTrade123`
- 添加 authtoken 丢失和双重认证问题解决方案
- 添加配置一致性检查建议

### 2026-04-04
- 添加登录弹窗修复（WWW-Authenticate 头）
- 配置 HTTP Basic Auth 认证

---

## 相关文档

- [02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md) - 系统配置详解
- [03_FLASK_ARCHITECTURE.md](03_FLASK_ARCHITECTURE.md) - Flask 架构文档
- [06_OPERATIONS.md](06_OPERATIONS.md) - 运维和故障排除
- [01_START_SERVER.md](01_START_SERVER.md) - 服务启动说明

---

**最后更新**: 2026-04-10
**维护人**: AI Assistant
**状态**: 文档已创建完成
