# 启动服务说明

## 📋 目录

- [服务架构](#服务架构)
- [快速启动](#快速启动)
- [配置参考](#配置参考)
- [验证步骤](#验证步骤)

---

## 服务架构

NeoTrade2 使用 macOS Launchd 自动启动服务：

```
┌─────────────────────────────────────────┐
│    macOS Launchd (自动启动)          │
│         ↓                            │
│   ┌──────────┴──────────┐         │
│   │                      │         │
│ Flask 服务           Cpolar 服务  │
│ (8765端口)        (外部隧道)    │
│   │                      │         │
│   └──────────┬──────────┘         │
│              ↓                     │
│         Dashboard               │
└─────────────────────────────────────────┘
```

---

## 快速启动

### 正常运行

服务通过 Launchd 自动管理，通常**无需手动启动**。

登录 macOS 时自动启动，异常退出后自动重启。

### 手动启动（仅用于开发调试）

如需手动启动，请参考 [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md) 中的详细命令。

---

## 配置参考

### 端口配置
详细端口配置请参考：[13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)

### 认证配置
详细认证配置（密码、用户名等）请参考：[02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)

### 服务管理
完整的服务管理命令（启动、停止、重启）请参考：[13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)

---

## 验证步骤

### 1. 检查服务状态

```bash
# 查看所有服务
launchctl list | grep -E "(neotrade|flask)"
```

应该看到：
- `com.neotrade2.flask` - Flask 服务
- `com.neotrade.cpolar` - Cpolar 服务

### 2. 测试本地访问

在浏览器访问 `http://localhost:8765/`

**预期结果**：
- 如果看到登录弹窗 → 服务正常运行
- 输入正确密码后可以访问 Dashboard

### 3. 测试外部访问

在浏览器访问 `https://neotrade.vip.cpolar.cn/`

**预期结果**：
- 如果看到登录弹窗 → Cpolar 隧道正常
- 输入正确密码后可以访问 Dashboard

### 4. 故障排查

如果访问失败，请参考以下文档：
- 服务问题 → [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)
- 认证问题 → [14_AUTHENTICATION_FIX.md](14_AUTHENTICATION_FIX.md)
- 系统配置 → [02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)

---

## 相关文档

- **[02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)** - 系统配置详解
- **[13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)** - 服务管理完整命令
- **[14_AUTHENTICATION_FIX.md](14_AUTHENTICATION_FIX.md)** - 认证故障排查
- **[06_OPERATIONS.md](06_OPERATIONS.md)** - 运维手册

---

**最后更新**: 2026-04-10
