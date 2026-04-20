# 每日筛选器 QA - Cron 配置文档

## 简介
每日筛选器 QA 脚本用于自动检查所有11个股票筛选器的运行状态，发现错误并生成报告。

## 文件位置
- **脚本**: `/Users/mac/.openclaw/workspace-neo/scripts/daily_screener_qa.py`
- **日志**: `/Users/mac/.openclaw/workspace-neo/logs/daily_qa_report_YYYY-MM-DD.json`
- **告警**: `/Users/mac/.openclaw/workspace-neo/alerts/screener_YYYY-MM-DD.json`

## 11个筛选器列表

| 序号 | ID | 名称 | 描述 |
|------|-----|------|------|
| 1 | coffee_cup_screener | 咖啡杯形态 | Coffee Cup Pattern Screener |
| 2 | jin_feng_huang_screener | 涨停金凤凰 | Jin Feng Huang Pattern |
| 3 | yin_feng_huang_screener | 涨停银凤凰 | Yin Feng Huang Pattern |
| 4 | shi_pan_xian_screener | 涨停试盘线 | Shi Pan Xian Pattern |
| 5 | er_ban_hui_tiao_screener | 二板回调 | Er Ban Hui Tiao Pattern |
| 6 | zhang_ting_bei_liang_yin_screener | 涨停倍量阴 | Zhang Ting Bei Liang Yin Pattern |
| 7 | breakout_20day_screener | 20日突破 | 20-Day Breakout Screener |
| 8 | breakout_main_screener | 主升突破 | Main Breakout Screener |
| 9 | daily_hot_cold_screener | 每日热冷股 | Daily Hot/Cold Stocks |
| 10 | shuang_shou_ban_screener | 双收板 | Shuang Shou Ban Pattern |
| 11 | ashare_21_screener | A股21选股 | A-Share 2.1 Selection |

## Cron 配置

### 每天 09:00 运行筛选器检查
```bash
# 编辑 crontab
crontab -e

# 添加以下行
0 9 * * * cd /Users/mac/.openclaw/workspace-neo && python3 scripts/daily_screener_qa.py >> logs/daily_screener_qa_cron.log 2>&1
```

### 或者在特定时间运行多个检查
```bash
# 每天 09:00、15:30 运行检查
0 9,15 * * * cd /Users/mac/.openclaw/workspace-neo && python3 scripts/daily_screener_qa.py >> logs/daily_screener_qa_cron.log 2>&1
```

## 手动运行

### 基本运行
```bash
cd /Users/mac/.openclaw/workspace-neo
python3 scripts/daily_screener_qa.py
```

### 指定日期检查
```bash
python3 scripts/daily_screener_qa.py --date 2026-03-18
```

### 详细输出
```bash
python3 scripts/daily_screener_qa.py --verbose
```

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 所有筛选器通过 |
| 1 | 有筛选器失败（少于3个） |
| 2 | 严重：3个或以上筛选器失败 |

## 报告格式

### 每日 QA 报告 (`logs/daily_qa_report_YYYY-MM-DD.json`)
```json
{
  "date": "2026-03-19",
  "timestamp": "2026-03-19T10:13:57.005297",
  "summary": {
    "total": 11,
    "passed": 0,
    "failed": 11,
    "warning": 0,
    "not_run": 0,
    "success_rate": 0.0,
    "total_errors": 11
  },
  "screeners": [...],
  "alerts": [...]
}
```

### 告警文件 (`alerts/screener_YYYY-MM-DD.json`)
```json
{
  "date": "2026-03-19",
  "timestamp": "2026-03-19T10:13:57.005632",
  "alert_count": 2,
  "alerts": [...]
}
```

## 告警级别

| 级别 | 条件 | 处理方式 |
|------|------|----------|
| 🔴 CRITICAL | ≥3个筛选器失败 | 立即人工介入 |
| 🟠 ERROR | 1-2个筛选器失败 | 检查并修复 |
| 🟡 WARNING | 有警告但未失败 | 关注 |

## 常见问题排查

### 1. 网络连接错误
**症状**: `ProxyError`, `MaxRetryError`, `RemoteDisconnected`
**原因**: 代理设置问题或网络不稳定
**解决**: 
```bash
# 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY

# 临时禁用代理测试
unset HTTP_PROXY HTTPS_PROXY
python3 scripts/daily_screener_qa.py
```

### 2. 脚本不存在
**症状**: `脚本文件不存在`
**解决**: 检查脚本路径是否正确

### 3. 输出目录不存在
**症状**: `输出目录不存在`
**解决**: 
```bash
mkdir -p scripts/data/screeners/{shuang_shou_ban,ashare_21}
```

## 监控集成

### 与现有监控系统集成
脚本生成的 JSON 报告可以被其他监控工具读取：

```bash
# 示例：检查今日是否有严重告警
python3 -c "
import json
from datetime import datetime
date = datetime.now().strftime('%Y-%m-%d')
with open(f'logs/daily_qa_report_{date}.json') as f:
    report = json.load(f)
    if report['summary']['failed'] >= 3:
        print('CRITICAL: Multiple screener failures')
        exit(2)
    elif report['summary']['failed'] > 0:
        print('WARNING: Some screeners failed')
        exit(1)
    else:
        print('OK: All screeners passed')
        exit(0)
"
```

## 维护

### 更新筛选器列表
编辑 `scripts/daily_screener_qa.py` 中的 `SCREENER_CONFIG` 字典。

### 调整告警阈值
编辑脚本中的 `generate_alerts()` 方法修改阈值。

## 联系
- **负责人**: Neo (Test Results Analyzer)
- **相关问题**: 数据工程师、DevOps 自动化工程师
