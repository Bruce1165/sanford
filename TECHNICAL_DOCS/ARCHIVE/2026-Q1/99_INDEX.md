# 技术文档索引

> NeoTrade2 技术文档的完整索引

## 📁 文档列表

### 快速入门
- **[00_START_HERE.md](00_START_HERE.md)** - 第一次来这里？从这开始
- **[01_START_SERVER.md](01_START_SERVER.md)** - Flask 启动和端口配置（已简化）
- **[02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md)** - 密码、认证、配置（唯一事实来源）

### 系统基础
- **[03_FLASK_ARCHITECTURE.md](03_FLASK_ARCHITECTURE.md)** - Flask 架构设计（已简化）
- **[13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md)** - Flask 和 Cpolar 服务管理（唯一事实来源）

### 架构和功能
- **[04_SCREENING_CONFIG.md](04_SCREENING_CONFIG.md)** - 筛选器参数配置系统
- **[05_DATA_PIPELINE.md](05_DATA_PIPELINE.md)** - 数据加载、更新、验证流程
- **[06_OPERATIONS.md](06_OPERATIONS.md)** - 运维手册和常见问题（已简化）
- **[08_API_REFERENCE.md](08_API_REFERENCE.md)** - API 端点和数据格式参考（唯一事实来源）

### 高级功能
- **[07_MONITORING.md](07_MONITORING.md)** - 监控配置和 Cron 任务
- **[09_SCREENERS_GUIDE.md](09_SCREENERS_GUIDE.md)** - 筛选器汇总和说明（包含已禁用筛选器列表）
- **[10_ONEIL_METHODS.md](10_ONEIL_METHODS.md)** - 欧奈尔形态技术白皮书
- **[11_COFFEE_CUP_PARAMS.md](11_COFFEE_CUP_PARAMS.md)** - 咖啡杯形态筛选器参数调整方案（旧版）
- **[11_COFFEE_CUP_PARAMS_V4.md](11_COFFEE_CUP_PARAMS_V4.md)** - 咖啡杯形态筛选器 V4参数（最新）
- **[15_SCREENER_MANAGEMENT.md](15_SCREENER_MANAGEMENT.md)** - 筛选器管理指南（添加/修改/删除）
- **[16_SCREENER_DISABLE_20260413.md](16_SCREENER_DISABLE_20260413.md)** - 2026-04-13 筛选器禁用记录（禁用 coffee_cup_screener 和 cup_handle_screener）
- **[14_AUTHENTICATION_FIX.md](14_AUTHENTICATION_FIX.md)** - 认证故障修复记录

### 归档（过时文档）
- **[ARCHIVE/](ARCHIVE/)** - 历史报告和过时技术文档

---

## 🔍 按主题查找

### 快速问题
| 问题 | 查看文档 |
|------|---------|
| 如何启动 Flask？ | [01_START_SERVER.md](01_START_SERVER.md) |
| 端口是多少？ | [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md) |
| 密码是什么？ | [02_SYSTEM_CONFIG.md](02_SYSTEM_CONFIG.md) |
| Cpolar 无法访问？ | [14_AUTHENTICATION_FIX.md](14_AUTHENTICATION_FIX.md) |
| 登录重复弹窗？ | [14_AUTHENTICATION_FIX.md](14_AUTHENTICATION_FIX.md) |
| 如何修改筛选器参数？ | [04_SCREENING_CONFIG.md](04_SCREENING_CONFIG.md) |
| 数据从哪里来？ | [05_DATA_PIPELINE.md](05_DATA_PIPELINE.md) |
| 服务管理命令？ | [13_FLASK_CPOLAR_SERVICES.md](13_FLASK_CPOLAR_SERVICES.md) |
| 常见错误解决？ | [06_OPERATIONS.md](06_OPERATIONS.md) |
| 如何启用/禁用筛选器？ | [09_SCREENERS_GUIDE.md](09_SCREENERS_GUIDE.md) |

### 深入问题
| 主题 | 查看文档 |
|------|---------|
| Flask 架构 | [03_FLASK_ARCHITECTURE.md](03_FLASK_ARCHITECTURE.md) |
| API 端点 | [08_API_REFERENCE.md](08_API_REFERENCE.md) |
| 监控设置 | [07_MONITORING.md](07_MONITORING.md) |
| 筛选器方法 | [09_SCREENERS_GUIDE.md](09_SCREENERS_GUIDE.md) 或 [10_ONEIL_METHODS.md](10_ONEIL_METHODS.md) |

---

## 📝 文档维护

### 更新规则
1. 每次架构变更后更新 `03_FLASK_ARCHITECTURE.md`
2. 新增 API 端点后更新 `08_API_REFERENCE.md`
3. 重要 Bug 修复后更新 `14_AUTHENTICATION_FIX.md`
4. 过时文档移到 ARCHIVE/

### 归档标准
- 2026 年以前的报告
- 已废弃的功能文档
- 临时分析文档

---

**最后更新**: 2026-04-13
