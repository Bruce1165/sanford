# Flask 服务自动启动配置

本目录包含 macOS Launchd 配置文件，用于自动管理 Flask 后端服务。

## 功能特性

- ✅ **开机自动启动**：系统启动后自动启动 Flask 服务
- ✅ **崩溃自动重启**：服务崩溃后自动重启（10秒间隔）
- ✅ **日志自动记录**：标准输出和错误分别记录到日志文件
- ✅ **用户级服务**：仅当前用户登录时运行

## 快速开始

### 安装服务

```bash
cd /Users/mac/NeoTrade2/scripts/launchd
./install_flask_service.sh
```

### 卸载服务

```bash
cd /Users/mac/NeoTrade2/scripts/launchd
./uninstall_flask_service.sh
```

## 手动管理命令

```bash
# 查看服务状态
launchctl list | grep com.neotrade2.flask

# 停止服务
launchctl stop com.neotrade2.flask

# 启动服务
launchctl start com.neotrade2.flask

# 重新加载配置
launchctl unload ~/Library/LaunchAgents/com.neotrade2.flask.plist
launchctl load ~/Library/LaunchAgents/com.neotrade2.flask.plist
```

## 日志文件

- **标准输出**: `/Users/mac/NeoTrade2/logs/flask.stdout.log`
- **错误输出**: `/Users/mac/NeoTrade2/logs/flask.stderr.log`

查看实时日志：
```bash
# 查看标准输出
tail -f /Users/mac/NeoTrade2/logs/flask.stdout.log

# 查看错误输出
tail -f /Users/mac/NeoTrade2/logs/flask.stderr.log

# 查看所有日志
tail -f /Users/mac/NeoTrade2/logs/flask.*.log
```

## 配置说明

| 配置项 | 值 | 说明 |
|--------|-----|------|
| Label | `com.neotrade2.flask` | 服务唯一标识 |
| Port | `8765` | Flask 服务端口 |
| Working Directory | `/Users/mac/NeoTrade2/backend` | 工作目录 |
| DASHBOARD_PASSWORD | `admin/bruce2024` | Dashboard 认证密码 |
| KeepAlive | `true` | 崩溃后自动重启 |
| RunAtLoad | `true` | 加载时立即启动 |
| ThrottleInterval | `10` | 重启间隔（秒） |

## 修改配置

如果需要修改配置（如端口、密码等），编辑以下文件：

```bash
# 编辑配置文件
vi /Users/mac/NeoTrade2/scripts/launchd/com.neotrade2.flask.plist
```

修改后需要重新加载服务：

```bash
# 卸载旧服务
launchctl unload ~/Library/LaunchAgents/com.neotrade2.flask.plist

# 重新安装
./install_flask_service.sh
```

## 常见问题

### 服务启动失败

1. 查看错误日志：
   ```bash
   tail -f /Users/mac/NeoTrade2/logs/flask.stderr.log
   ```

2. 检查端口是否被占用：
   ```bash
   lsof -i :8765
   ```

3. 手动测试启动：
   ```bash
   cd /Users/mac/NeoTrade2/backend
   DASHBOARD_PASSWORD=admin/bruce2024 python3 app.py --port 8765
   ```

### 服务频繁重启

如果服务频繁重启，可能是配置错误或代码异常。

1. 查看 ThrottleInterval 设置（当前为 10 秒）
2. 查看错误日志定位问题
3. 修复问题后使用 `launchctl start` 手动启动

### 查看服务详细信息

```bash
# 查看完整配置
launchctl list com.neotrade2.flask

# 查看进程信息
ps aux | grep "python3.*app.py"
```

## 手动启动（开发模式）

如需手动启动（不使用 Launchd）：

```bash
cd /Users/mac/NeoTrade2/backend
DASHBOARD_PASSWORD=admin/bruce2024 python3 app.py --port 8765
```

注意：手动启动前需要先停止 Launchd 服务，避免端口冲突。
