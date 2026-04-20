# Neo股票数据分析系统 - 监控配置指南

**版本**: 1.0  
**创建日期**: 2026-03-19  
**维护者**: SRE Team

---

## 目录

1. [概述](#概述)
2. [组件说明](#组件说明)
3. [安装配置](#安装配置)
4. [Cron定时任务](#cron定时任务)
5. [告警说明](#告警说明)
6. [故障排查](#故障排查)

---

## 概述

数据健康监控系统用于确保Neo股票数据分析系统的数据质量和及时性。

### 监控项

| 检查项 | 说明 | 阈值 |
|--------|------|------|
| 数据新鲜度 | 最新数据日期是否为最近交易日 | 延迟 ≤ 0 天 |
| 股票完整性 | 最新日期是否包含全部4663只股票 | 缺失 = 0 |
| 重复数据 | 是否有违反唯一约束的记录 | 重复组 = 0 |
| 数据质量 | 异常价格、零成交量、缺失价格 | 无异常 |

### 文件结构

```
workspace-neo/
├── scripts/
│   └── data_health_check.py    # 健康检查脚本
├── logs/
│   └── data_health.log         # 检查日志
├── alerts/
│   ├── 2026-03-19_alert.json   # 正常状态示例
│   └── 2026-03-17_alert.json   # 异常告警示例
└── docs/
    └── monitoring_setup.md      # 本文档
```

---

## 组件说明

### 1. 健康检查脚本 (`scripts/data_health_check.py`)

#### 功能
- 检查数据新鲜度
- 验证股票数量完整性
- 检测重复数据
- 检查数据质量问题

#### 用法

```bash
# 基本用法
python scripts/data_health_check.py

# 指定数据库路径
python scripts/data_health_check.py --db /path/to/stock_data.db

# 输出报告到文件
python scripts/data_health_check.py -o report.json

# 静默模式（只输出JSON结果）
python scripts/data_health_check.py -q
```

#### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 系统健康 |
| 1 | 发现问题 |

#### 报告格式

```json
{
  "timestamp": "2026-03-19T09:00:05",
  "status": "healthy|warning|fail|critical",
  "checks": {
    "data_freshness": { ... },
    "stock_completeness": { ... },
    "duplicate_data": { ... },
    "data_quality": { ... }
  },
  "alerts": [],
  "alert_file": "alerts/2026-03-19_alert.json"
}
```

### 2. 日志文件 (`logs/data_health.log`)

- 记录所有检查操作的详细日志
- 包含时间戳、日志级别、消息
- 保留历史记录用于审计

### 3. 告警文件 (`alerts/YYYY-MM-DD_alert.json`)

- 当发现问题时自动生成
- 包含完整的检查报告
- 支持多个告警追加到同一文件

---

## 安装配置

### 1. 确保Python环境

```bash
# 检查Python版本（需要3.7+）
python3 --version

# 安装依赖（通常只需要标准库）
# 本项目不依赖外部包
```

### 2. 设置文件权限

```bash
# 确保脚本可执行
chmod +x scripts/data_health_check.py

# 确保目录权限正确
chmod 755 logs alerts
```

### 3. 测试运行

```bash
# 在项目根目录运行
cd /Users/mac/.openclaw/workspace-neo
python scripts/data_health_check.py
```

---

## Cron定时任务

### 推荐配置

编辑 crontab:

```bash
crontab -e
```

添加以下配置:

```cron
# Neo股票数据健康检查 - 每小时运行一次
0 * * * * cd /Users/mac/.openclaw/workspace-neo && /usr/bin/python3 scripts/data_health_check.py >> logs/cron_health_check.log 2>&1

# 每日状态报告 - 08:30发送（可在报告中添加邮件/钉钉通知）
30 8 * * * cd /Users/mac/.openclaw/workspace-neo && /usr/bin/python3 scripts/data_health_check.py -o logs/daily_report_$(date +\%Y\%m\%d).json

# 清理旧告警文件 - 每月1日清理90天前的告警
0 0 1 * * find /Users/mac/.openclaw/workspace-neo/alerts -name "*_alert.json" -mtime +90 -delete
```

### macOS LaunchAgent 配置（推荐）

创建 plist 文件:

```bash
cat > ~/Library/LaunchAgents/com.neo.data-health-check.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neo.data-health-check</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/mac/.openclaw/workspace-neo/scripts/data_health_check.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/mac/.openclaw/workspace-neo</string>
    <key>StartCalendarInterval</key>
    <array>
        <!-- 每小时运行 -->
        <dict>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
    <key>StandardOutPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_health_check.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_health_check_error.log</string>
</dict>
</plist>
EOF
```

加载配置:

```bash
launchctl load ~/Library/LaunchAgents/com.neo.data-health-check.plist
launchctl start com.neo.data-health-check
```

---

## 告警说明

### 告警级别

| 级别 | 说明 | 响应时间 |
|------|------|----------|
| `critical` | 严重问题（数据库连接失败、大量重复数据） | 立即处理 |
| `fail` | 检查失败（数据延迟、完整性问题） | 1小时内 |
| `warning` | 警告（少量缺失、数据质量问题） | 4小时内 |

### 告警类型

| 类型 | 说明 |
|------|------|
| `database_connection_error` | 数据库连接失败 |
| `data_stale` | 数据延迟 |
| `incomplete_data` | 股票数据不完整 |
| `duplicate_data` | 发现重复数据 |
| `extreme_price_change` | 异常价格变动 |
| `zero_volume` | 零成交量记录 |
| `missing_prices` | 价格数据缺失 |

### 状态值

| 状态 | 说明 |
|------|------|
| `healthy` | 全部检查通过 |
| `warning` | 有警告但无严重问题 |
| `fail` | 有检查项失败 |
| `critical` | 严重错误 |
| `error` | 检查执行出错 |
| `pass` | 单个检查通过 |

---

## 故障排查

### 问题1: 脚本执行失败

**症状**: 运行脚本时报错

**排查步骤**:
1. 检查Python版本: `python3 --version`
2. 检查数据库文件是否存在: `ls -la data/stock_data.db`
3. 检查文件权限: `ls -la scripts/data_health_check.py`
4. 查看详细错误: `python scripts/data_health_check.py 2>&1`

### 问题2: 数据库连接失败

**症状**: 日志显示 "数据库连接失败"

**排查步骤**:
1. 检查数据库文件是否存在
2. 检查文件权限: `chmod 644 data/stock_data.db`
3. 检查磁盘空间: `df -h`
4. 尝试手动连接: `sqlite3 data/stock_data.db ".tables"`

### 问题3: Cron任务不执行

**症状**: 定时任务没有产生日志

**排查步骤**:
1. 检查cron服务状态: `sudo launchctl list | grep cron`
2. 检查crontab语法: `crontab -l`
3. 检查日志文件权限
4. 测试手动执行cron命令

### 问题4: 重复数据告警

**症状**: 检测到重复数据

**处理步骤**:
1. 查看告警详情: `cat alerts/YYYY-MM-DD_alert.json`
2. 手动检查重复: 
   ```sql
   SELECT code, trade_date, COUNT(*) as cnt
   FROM daily_prices
   GROUP BY code, trade_date
   HAVING cnt > 1;
   ```
3. 清理重复数据（谨慎操作）
4. 检查数据导入脚本逻辑

---

## 扩展功能

### 添加邮件通知

修改脚本，在发现问题时发送邮件:

```python
import smtplib
from email.mime.text import MIMEText

def send_alert_email(report):
    if report["status"] != "healthy":
        msg = MIMEText(json.dumps(report, indent=2))
        msg['Subject'] = f'[ALERT] Neo数据健康检查 - {report["status"]}'
        msg['From'] = 'alert@neo.local'
        msg['To'] = 'admin@example.com'
        
        with smtplib.SMTP('localhost') as s:
            s.send_message(msg)
```

### 集成到Dashboard

可以在Dashboard中添加健康检查状态显示:

```python
# dashboard/app.py
@app.route('/api/health')
def health_status():
    report = check_data_health()
    return jsonify(report)
```

---

## 更新记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-03-19 | 1.0 | 初始版本 |

---

## 联系方式

- **SRE负责人**: engineering-sre
- **紧急联系**: Neo (Project Manager)
