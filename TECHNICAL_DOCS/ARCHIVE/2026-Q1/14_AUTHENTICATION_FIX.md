# Cpolar 认证故障修复记录

**Date**: 2026-04-10  
**Version**: 1.0  
**Purpose**: 记录 Cpolar 隧道外部 URL 无法访问的问题分析和解决方案

---

## 📋 目录

- [问题现象](#问题现象)
- [根因分析](#根因分析)
- [解决步骤](#解决步骤)
- [预防措施](#预防措施)

---

## 问题现象

### 初期症状

1. **外部 URL 无法访问**
   - `https://neotrade.vip.cpolar.cn` 无法连接
   - 内部 URL `http://localhost:8765` 正常工作

2. **登录弹窗重复出现**
   - 访问外部 URL 时连续弹出两个登录框
   - Flask 和 Cpolar 都要求认证
   - 两个系统的用户名密码不一致，无法登录

### 错误日志

Cpolar 日志显示：
```
time="2026-04-10T17:28:11+08:00" level=error msg="启动时没有authtoken"
not found authtoken.
```

---

## 根因分析

### 问题 1：Authtoken 丢失

**原因**：
- `~/.cpolar/cpolar.yml` 配置文件为空（0 字节）
- Cpolar 无法连接到认证服务器
- 导致隧道无法建立

**验证方法**：
```bash
# 检查配置文件大小
ls -la ~/.cpolar/cpolar.yml

# 查看 authtoken
cpolar authtoken  # 如果丢失会报错
```

### 问题 2：双重认证冲突

**原因**：
- Flask Basic Auth（通过 Launchd 配置）
- Cpolar HTTP Auth（通过启动脚本 `--httpauth` 参数）
- 两个认证层使用不同的密码

**配置文件对比**：

| 服务 | 配置位置 | 密码 |
|------|---------|------|
| Flask | `~/Library/LaunchAgents/com.neotrade2.flask.plist` | `admin/bruce2024` (错误格式) |
| Cpolar | `/Users/mac/start_cpolar_auth.sh` | `admin:NeoTrade` |

### 问题 3：Flask 密码格式错误

Launchd 配置中密码值为：
```xml
<string>admin/bruce2024</string>
```

**问题**：
- 值包含用户名和密码组合
- Flask 的 Basic Auth 验证逻辑是 `password == DASHBOARD_PASSWORD`
- 用户名部分导致验证失败

**正确的配置应该是纯密码**：
```xml
<string>NeoTrade123</string>
```

---

## 解决步骤

### 步骤 1：获取 Cpolar Authtoken

访问 Cpolar Dashboard 获取 authtoken：
1. 登录 https://dashboard.cpolar.cn/login
2. 点击左侧菜单 **"验证"** 或 **"Authtoken"**
3. 复制 authtoken

### 步骤 2：配置 Authtoken

```bash
# 设置 authtoken
cpolar authtoken <你的authtoken>

# 验证已保存
cat ~/.cpolar/cpolar.yml
```

### 步骤 3：使用 Launchd 正确重启服务

**错误方法**（不要使用）：
```bash
pkill -f cpolar
pkill -f flask
```

**正确方法**：
```bash
# 停止服务
launchctl stop com.neotrade.cpolar
launchctl stop com.neotrade2.flask

# 卸载配置
launchctl unload ~/Library/LaunchAgents/com.neotrade.cpolar.plist
launchctl unload ~/Library/LaunchAgents/com.neotrade2.flask.plist
```

### 步骤 4：修正 Flask 密码配置

编辑 `~/Library/LaunchAgents/com.neotrade2.flask.plist`：

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>DASHBOARD_PASSWORD</key>
    <string>NeoTrade123</string>  <!-- 纯密码，不要包含用户名 -->
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
</dict>
```

**注意**：密码要与 `config/.env` 中的 `DASHBOARD_PASSWORD` 保持一致。

### 步骤 5：移除 Cpolar HTTP 认证

编辑 `/Users/mac/start_cpolar_auth.sh`：

```bash
# 删除 --httpauth 参数
/usr/local/bin/cpolar http 8765 --subdomain=neotrade --region=cn_vip --log=/Users/mac/neotrade_cpolar.log --log-level=info
```

**原因**：
- Flask 已经提供 Basic Auth 保护
- Cpolar 的 HTTP 认证是冗余的
- 移除后只保留一层认证，避免双重登录

### 步骤 6：重新加载配置

```bash
# 加载配置
launchctl load ~/Library/LaunchAgents/com.neotrade.cpolar.plist
launchctl load ~/Library/LaunchAgents/com.neotrade2.flask.plist

# 等待服务启动
sleep 10

# 查看服务状态
launchctl list | grep -E "(cpolar|flask)"
```

### 步骤 7：验证服务正常

```bash
# 检查 Cpolar 隧道
tail -10 /Users/mac/neotrade_cpolar.log
# 应该看到：Tunnel established at https://neotrade.vip.cpolar.cn

# 测试本地服务
curl -s -o /dev/null -w "HTTP 状态码: %{http_code}\n" http://localhost:8765/
# 应该返回：HTTP 状态码: 401

# 测试外部 URL
curl -s -u "any:NeoTrade123" -k https://neotrade.vip.cpolar.cn/ | grep "NEO Dashboard"
# 应该看到页面标题
```

---

## 预防措施

### 1. 备份配置文件

定期备份关键配置，详细操作请参考 [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)。

### 2. 配置一致性检查

确保配置文件中的密码一致，详细配置请参考 [02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)。

### 3. 避免双重认证

**认证层级原则**：
- Flask Basic Auth 提供应用层保护
- Cpolar 只做隧道转发，不需要额外认证
- 保持单一认证层，提升用户体验

### 4. 使用 Launchd 管理服务

正确的工作流和命令请参考 [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)。

### 5. 监控服务健康

定期检查服务状态，详细命令请参考 [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)。

---

## 当前访问信息

| 项目 | 值 |
|------|-----|
| 外部 URL | https://neotrade.vip.cpolar.cn |
| 本地 URL | http://localhost:8765 |
| 认证类型 | Flask Basic Auth |
| 用户名 | 任意 |
| 密码 | NeoTrade123 |
| 认证层级 | 单层（仅 Flask） |

---

## 相关文档

- **[02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)** - 密码和认证配置
- **[13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)** - Flask 和 Cpolar 服务架构
- **[06_OPERATIONS.md](06_OPERATIONS.md)** - 运维手册和常见问题

---

**最后更新**: 2026-04-10
