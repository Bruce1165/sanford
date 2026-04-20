# Neo量化研究体系 - Cron定时任务配置

## 任务概览

| 任务 | 执行时间 | 执行脚本 | 输出 |
|------|----------|----------|------|
| 盘中-指数观测 | 9:35, 9:45 | intraday_task.py --type index | MD日志 |
| 盘中-涨跌分析 | 10:00, 15:00 | intraday_task.py --type analysis | MD + Excel |
| 盘后-深度复盘 | 15:30 | postmarket_task.py | MD + Excel |

## 目录结构

```
workspace-neo/
├── data/
│   ├── intraday/              # 盘中数据
│   │   └── 2026-03-11/
│   │       ├── 0935_index.md
│   │       ├── 0945_index.md
│   │       ├── 1000_limit_up.md
│   │       ├── 1000_limit_up.xlsx
│   │       ├── 1000_weak.md
│   │       ├── 1000_weak.xlsx
│   │       ├── 1500_limit_up.md
│   │       └── 1500_limit_up.xlsx
│   └── postmarket/            # 盘后数据
│       └── 2026-03-11/
│           ├── daily_review.md
│           └── daily_review.xlsx
├── logs/
│   ├── intraday_20260311.log
│   └── postmarket_20260311.log
└── scripts/cron/
    ├── intraday_task.py
    └── postmarket_task.py
```

## Mac launchd 配置

### 1. 盘中任务 - 9:35

创建 `~/Library/LaunchAgents/com.neo.intraday.0935.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neo.intraday.0935</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>/Users/mac/.openclaw/workspace-neo/scripts/cron/intraday_task.py</string>
        <string>--type</string>
        <string>index</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>35</integer>
        <key>Weekday</key>
        <integer>1</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_0935.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_0935_error.log</string>
</dict>
</plist>
```

### 2. 盘中任务 - 9:45

创建 `~/Library/LaunchAgents/com.neo.intraday.0945.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neo.intraday.0945</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>/Users/mac/.openclaw/workspace-neo/scripts/cron/intraday_task.py</string>
        <string>--type</string>
        <string>index</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>45</integer>
        <key>Weekday</key>
        <integer>1</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_0945.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_0945_error.log</string>
</dict>
</plist>
```

### 3. 盘中任务 - 10:00

创建 `~/Library/LaunchAgents/com.neo.intraday.1000.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neo.intraday.1000</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>/Users/mac/.openclaw/workspace-neo/scripts/cron/intraday_task.py</string>
        <string>--type</string>
        <string>analysis</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
        <key>Weekday</key>
        <integer>1</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_1000.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_1000_error.log</string>
</dict>
</plist>
```

### 4. 盘中任务 - 15:00

创建 `~/Library/LaunchAgents/com.neo.intraday.1500.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neo.intraday.1500</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>/Users/mac/.openclaw/workspace-neo/scripts/cron/intraday_task.py</string>
        <string>--type</string>
        <string>analysis</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>15</integer>
        <key>Minute</key>
        <integer>0</integer>
        <key>Weekday</key>
        <integer>1</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_1500.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_1500_error.log</string>
</dict>
</plist>
```

### 5. 盘后任务 - 15:30

创建 `~/Library/LaunchAgents/com.neo.postmarket.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neo.postmarket</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>/Users/mac/.openclaw/workspace-neo/scripts/cron/postmarket_task.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>15</integer>
        <key>Minute</key>
        <integer>30</integer>
        <key>Weekday</key>
        <integer>1</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_postmarket.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_postmarket_error.log</string>
</dict>
</plist>
```

## 加载定时任务

```bash
# 加载所有任务
launchctl load ~/Library/LaunchAgents/com.neo.intraday.0935.plist
launchctl load ~/Library/LaunchAgents/com.neo.intraday.0945.plist
launchctl load ~/Library/LaunchAgents/com.neo.intraday.1000.plist
launchctl load ~/Library/LaunchAgents/com.neo.intraday.1500.plist
launchctl load ~/Library/LaunchAgents/com.neo.postmarket.plist

# 查看任务状态
launchctl list | grep com.neo

# 手动运行测试
python3 /Users/mac/.openclaw/workspace-neo/scripts/cron/intraday_task.py --type index
python3 /Users/mac/.openclaw/workspace-neo/scripts/cron/postmarket_task.py

# 卸载任务（如需修改）
launchctl unload ~/Library/LaunchAgents/com.neo.intraday.0935.plist
```

## 注意事项

1. **Weekday设置**: 当前配置为周一(1)，需要改为周一到周五(1-5)
2. **节假日**: 脚本内部会检查是否交易日，非交易日自动跳过
3. **依赖安装**: 确保已安装 `pip install akshare pandas openpyxl`
4. **权限**: 首次运行可能需要授权

## 修改建议

当前配置只设置了周一(Weekday=1)，需要修改为周一到周五：

```xml
<key>Weekday</key>
<integer>1</integer>
```

改为多个plist文件，每个对应一天，或者使用cron（更灵活）。

---

*配置版本: v1.0*
*创建日期: 2026-03-11*
