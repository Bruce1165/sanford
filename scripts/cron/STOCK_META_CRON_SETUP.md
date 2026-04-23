# stock_meta 日检 cron 配置

## 1) 任务说明

- 任务脚本：`scripts/cron/stock_meta_freshness_task.py`
- 校验脚本：`scripts/check_stock_meta_freshness.py`
- 默认阈值：
- `update_ratio >= 0.90`
- `sector_ratio >= 0.95`
- 默认时间：每日 `22:30`

## 2) 安装 launchd 任务

```bash
cp /Users/mac/NeoTrade2/scripts/cron/com.neotrade.stock_meta_freshness.plist \
  ~/Library/LaunchAgents/com.neotrade.stock_meta_freshness.plist

launchctl unload ~/Library/LaunchAgents/com.neotrade.stock_meta_freshness.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.neotrade.stock_meta_freshness.plist
```

## 3) 查看状态与手动触发

```bash
launchctl list | grep com.neotrade.stock_meta_freshness

# 手动触发一次（推荐先验证）
launchctl start com.neotrade.stock_meta_freshness
```

## 4) 日志位置

- `logs/stock_meta_freshness.log`
- `logs/stock_meta_freshness_error.log`
- `logs/stock_meta_freshness_cron.log`

## 5) 调整执行时间

修改 `scripts/cron/com.neotrade.stock_meta_freshness.plist` 中：

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>22</integer>
    <key>Minute</key>
    <integer>30</integer>
</dict>
```

修改后重新加载：

```bash
launchctl unload ~/Library/LaunchAgents/com.neotrade.stock_meta_freshness.plist
launchctl load ~/Library/LaunchAgents/com.neotrade.stock_meta_freshness.plist
```

## 6) 定向补齐（网络恢复后手动执行）

- 重试清单：`scripts/cron/stock_meta_retry_codes.txt`
- 任务脚本：`scripts/cron/stock_meta_retry_task.py`
- 失败清单输出：`scripts/cron/stock_meta_retry_failed.txt`

```bash
python3 scripts/cron/stock_meta_retry_task.py
```

如果需要自定义参数：

```bash
python3 scripts/cron/stock_meta_retry_task.py \
  --codes-file scripts/cron/stock_meta_retry_codes.txt \
  --login-retry 5 \
  --query-retry 4 \
  --retry-delay 1.2
```
