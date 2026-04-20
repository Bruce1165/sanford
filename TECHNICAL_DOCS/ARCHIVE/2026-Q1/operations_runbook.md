# Neo股票数据分析系统 - 运维手册

> **版本**: 1.0  
> **更新日期**: 2026-03-19  
> **紧急联系人**: Bruce  

---

## 1. 日常检查清单

### 1.1 每日必检项 (08:30)

```bash
#!/bin/bash
# daily_check.sh - 每日检查脚本

echo "=== Neo系统每日检查 $(date) ==="

# 1. 检查Dashboard服务
echo "[1/7] 检查Dashboard服务..."
if pgrep -f "dashboard/app.py" > /dev/null; then
    echo "  ✓ Dashboard运行中"
else
    echo "  ✗ Dashboard未运行，启动中..."
    python3 dashboard/app.py &
fi

# 2. 检查数据更新状态
echo "[2/7] 检查数据更新状态..."
python3 -c "
import json
from pathlib import Path
progress_file = Path('data/daily_update_progress_v2.json')
if progress_file.exists():
    data = json.load(open(progress_file))
    completed = len(data.get('completed', []))
    print(f'  进度: {completed}/4663 ({completed/4663*100:.1f}%)')
    print(f'  状态: {data.get(\"status\", \"unknown\")}')
else:
    print('  无进度文件')
"

# 3. 检查数据库大小
echo "[3/7] 检查数据库..."
DB_SIZE=$(stat -f%z data/stock_data.db 2>/dev/null || stat -c%s data/stock_data.db 2>/dev/null)
DB_SIZE_MB=$((DB_SIZE / 1024 / 1024))
echo "  数据库大小: ${DB_SIZE_MB}MB"

# 4. 检查磁盘空间
echo "[4/7] 检查磁盘空间..."
df -h . | tail -1 | awk '{print "  可用: "$4 " (" $5 "已用)"}'

# 5. 检查昨日筛选结果
echo "[5/7] 检查昨日筛选结果..."
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
for screener in coffee_cup jin_feng_huang er_ban_hui_tiao; do
    count=$(ls data/screeners/${screener}/${YESTERDAY}.xlsx 2>/dev/null | wc -l)
    if [ "$count" -gt 0 ]; then
        echo "  ✓ ${screener}: 有结果"
    else
        echo "  - ${screener}: 无结果"
    fi
done

# 6. 检查日志错误
echo "[6/7] 检查近期错误..."
grep -i "error" logs/*.log 2>/dev/null | tail -5 || echo "  无错误日志"

# 7. 检查备份状态
echo "[7/7] 检查备份状态..."
ls -lt data/*.db.bak* 2>/dev/null | head -1 | awk '{print "  最近备份: "$9 " (" $6, $7, $8 ")"}' || echo "  无备份文件"

echo "=== 检查完成 ==="
```

### 1.2 每周必检项 (周五)

- [ ] **数据完整性**: 运行 `python3 check_integrity.py`
- [ ] **磁盘清理**: 清理30天前的日志 `find logs -name "*.log" -mtime +30 -delete`
- [ ] **备份验证**: 测试备份文件能否正常打开
- [ ] **依赖更新**: 检查Python包更新 `pip3 list --outdated`
- [ ] **安全审计**: 检查是否有异常进程或文件

### 1.3 每月必检项

- [ ] **全量数据校验**: 对比Baostock数据完整性
- [ ] **性能基准测试**: 记录筛选器运行时间
- [ ] **数据库优化**: VACUUM和索引检查
- [ ] **文档更新**: 检查文档是否与实际系统一致
- [ ] **灾备演练**: 模拟恢复流程

---

## 2. 故障排查步骤

### 2.1 故障分类与响应

```
┌──────────────────────────────────────────────────────────────┐
│                     故障响应流程                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  P0 - 系统瘫痪                                                │
│  ├── 数据无法更新                                             │
│  ├── 数据库损坏                                               │
│  └── 响应时间: 立即 → 联系Bruce                               │
│                                                              │
│  P1 - 功能受损                                                │
│  ├── 单个筛选器失败                                           │
│  ├── Dashboard无法访问                                        │
│  └── 响应时间: 2小时内                                        │
│                                                              │
│  P2 - 性能下降                                                │
│  ├── 查询缓慢                                                 │
│  ├── 更新延迟                                                 │
│  └── 响应时间: 24小时内                                       │
│                                                              │
│  P3 - 轻微问题                                                │
│  ├── 日志警告                                                 │
│  ├── 非关键功能异常                                           │
│  └── 响应时间: 下次维护窗口                                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 常见故障排查

#### 故障1: 数据更新失败

**症状**: `daily_update_progress_v2.json` 状态为 `running` 超过1小时无变化

**排查步骤**:
```bash
# 1. 检查进程是否存在
ps aux | grep daily_update_screener

# 2. 检查日志
tail -100 logs/daily_update_$(date +%Y%m%d).log

# 3. 检查网络连接
ping www.baostock.com

# 4. 检查Baostock登录
curl -I https://www.baostock.com

# 5. 解决方案
# 如果进程卡住
pkill -f daily_update_screener

# 重新运行
python3 scripts/daily_update_screener.py --loop
```

#### 故障2: 数据库锁定

**症状**: `sqlite3.OperationalError: database is locked`

**排查步骤**:
```bash
# 1. 查找锁定进程
lsof data/stock_data.db

# 2. 检查是否有僵尸进程
ps aux | grep python3 | grep -v grep

# 3. 解决方案
# 终止所有相关进程
pkill -f "python3.*screener"

# 等待10秒后检查
sleep 10
lsof data/stock_data.db

# 如果仍被锁定，重启Dashboard
pkill -f "dashboard/app.py"
sleep 5
python3 dashboard/app.py &
```

#### 故障3: 筛选器无结果

**症状**: 所有筛选器连续多日返回空结果

**排查步骤**:
```bash
# 1. 检查最新数据日期
sqlite3 data/stock_data.db "SELECT MAX(trade_date) FROM daily_prices;"

# 2. 检查数据条数
sqlite3 data/stock_data.db "SELECT COUNT(*) FROM daily_prices WHERE trade_date = '$(date -v-1d +%Y-%m-%d)';"

# 3. 对比实际交易日
python3 scripts/trading_calendar.py

# 4. 如果数据缺失，手动触发更新
python3 scripts/daily_update_screener.py --date $(date -v-1d +%Y-%m-%d) --loop
```

#### 故障4: Dashboard 500错误

**症状**: 网页显示Internal Server Error

**排查步骤**:
```bash
# 1. 查看Dashboard日志
tail -100 logs/dashboard.log

# 2. 检查数据库连接
sqlite3 data/stock_data.db ".tables"

# 3. 检查端口占用
lsof -i :5003

# 4. 重启Dashboard
pkill -f "dashboard/app.py"
sleep 2
cd dashboard && python3 app.py > ../logs/dashboard.log 2>&1 &
```

#### 故障5: 磁盘空间不足

**症状**: `OSError: [Errno 28] No space left on device`

**排查步骤**:
```bash
# 1. 检查空间使用
du -sh *

# 2. 清理日志
find logs -name "*.log" -size +100M -delete
find logs -name "*.log" -mtime +30 -delete

# 3. 清理旧备份
ls -t data/*.db.bak* | tail -n +5 | xargs rm -f

# 4. 清理旧筛选结果
find data/screeners -name "*.xlsx" -mtime +90 -delete

# 5. 数据库VACUUM(释放已删除空间)
sqlite3 data/stock_data.db "VACUUM;"
```

### 2.3 诊断命令速查

| 问题 | 诊断命令 |
|------|---------|
| 查看进程 | `ps aux \| grep python3` |
| 查看端口 | `lsof -i :5003` |
| 查看磁盘 | `df -h` |
| 查看内存 | `free -h` 或 `vm_stat` |
| 数据库检查 | `sqlite3 data/stock_data.db "PRAGMA integrity_check;"` |
| 网络测试 | `ping www.baostock.com` |
| 日志追踪 | `tail -f logs/*.log` |

---

## 3. 紧急联系人与升级流程

### 3.1 联系人信息

| 角色 | 姓名 | 联系方式 | 职责 |
|------|------|---------|------|
| **项目负责人** | Bruce | [配置] | 重大决策、资源协调 |
| **技术负责人** | Neo Agent | 系统内 | 技术方案、故障处理 |
| **数据工程师** | Data Agent | 系统内 | 数据问题、ETL故障 |
| **运维工程师** | DevOps Agent | 系统内 | 部署、监控、基础设施 |

### 3.2 升级流程

```
发现问题
    │
    ├── 能否自行解决? ── 是 → 修复并记录
    │
    └── 否
        │
        ▼
评估影响范围
    │
    ├── P0/P1 (影响核心功能)
    │   │
    │   └── 立即联系Bruce
    │       └── 15分钟内响应
    │
    └── P2/P3 (影响非核心功能)
        │
        └── 记录问题
            └── 下次维护窗口处理
```

### 3.3 紧急联系模板

```
【紧急】Neo系统故障 - P0/P1

时间: 2026-03-19 09:30
故障现象: [简述问题]
影响范围: [数据更新/筛选器/Dashboard/全部]
已采取措施: [已执行的操作]
需要支持: [需要决策/资源/协助]

日志片段:
[关键错误日志]
```

---

## 4. 回滚和恢复流程

### 4.1 数据回滚

#### 场景: 当日数据污染

```bash
# 1. 停止所有写入操作
pkill -f "daily_update_screener.py"
pkill -f "run_all_screeners.py"

# 2. 备份当前状态(用于事后分析)
cp data/stock_data.db data/stock_data.db.corrupt.$(date +%Y%m%d%H%M)
cp data/daily_update_progress_v2.json data/daily_update_progress_v2.json.bak

# 3. 恢复到昨日备份
LATEST_BACKUP=$(ls -t data/stock_data.db.bak* | head -1)
cp "$LATEST_BACKUP" data/stock_data.db

# 4. 清理今日进度
rm -f data/daily_update_progress_v2.json

# 5. 重新执行今日更新
python3 scripts/daily_update_screener.py --date $(date +%Y-%m-%d) --loop

# 6. 验证
sqlite3 data/stock_data.db "SELECT COUNT(*) FROM daily_prices WHERE trade_date = '$(date +%Y-%m-%d)';"
```

### 4.2 配置回滚

```bash
# 1. 回滚到上一版本
git log --oneline -5  # 查看提交历史
git revert HEAD       # 回滚最近一次提交
# 或
git checkout [commit_hash] -- [file_path]  # 回滚特定文件

# 2. 重启服务
pkill -f "dashboard/app.py"
python3 dashboard/app.py &
```

### 4.3 完整系统恢复

#### 场景: 灾难恢复

```bash
#!/bin/bash
# disaster_recovery.sh - 灾难恢复脚本

RECOVERY_DATE="2026-03-18"
BACKUP_DIR="/path/to/offsite/backup"

echo "=== 开始灾难恢复 ==="

# 1. 停止所有服务
pkill -f python3
sleep 5

# 2. 清理损坏的数据
mv data/stock_data.db data/stock_data.db.destroyed.$(date +%Y%m%d%H%M)
rm -rf data/screeners/*

# 3. 从异地备份恢复
cp "${BACKUP_DIR}/stock_data.db.${RECOVERY_DATE}" data/stock_data.db
cp -r "${BACKUP_DIR}/screeners.${RECOVERY_DATE}"/* data/screeners/

# 4. 验证数据库
sqlite3 data/stock_data.db "PRAGMA integrity_check;"

# 5. 恢复进度文件
cp "${BACKUP_DIR}/daily_update_progress_v2.json.${RECOVERY_DATE}" data/daily_update_progress_v2.json

# 6. 启动服务
python3 dashboard/app.py &

# 7. 补录缺失数据
python3 scripts/daily_update_screener.py --loop

echo "=== 灾难恢复完成 ==="
```

### 4.4 备份策略

```bash
#!/bin/bash
# backup.sh - 自动备份脚本

BACKUP_DIR="/Users/mac/Backups/neo/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# 1. 备份数据库
cp data/stock_data.db "$BACKUP_DIR/"

# 2. 备份关键配置
cp -r config "$BACKUP_DIR/"
cp dashboard/app.py "$BACKUP_DIR/"
cp scripts/daily_update_screener.py "$BACKUP_DIR/"

# 3. 备份进度文件
cp data/daily_update_progress_v2.json "$BACKUP_DIR/"

# 4. 备份筛选结果(最近7天)
find data/screeners -name "*.xlsx" -mtime -7 -exec cp {} "$BACKUP_DIR/" \;

# 5. 压缩
tar -czf "${BACKUP_DIR}.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

# 6. 清理旧备份(保留30天)
find /Users/mac/Backups/neo -name "*.tar.gz" -mtime +30 -delete

echo "备份完成: ${BACKUP_DIR}.tar.gz"
```

---

## 5. 监控与告警

### 5.1 关键指标监控

```python
# monitoring.py - 关键指标检查
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

def check_data_freshness():
    """检查数据新鲜度"""
    conn = sqlite3.connect('data/stock_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
    latest_date = cursor.fetchone()[0]
    conn.close()
    
    today = datetime.now().date()
    latest = datetime.strptime(latest_date, '%Y-%m-%d').date()
    
    if (today - latest).days > 1:
        return False, f"数据延迟: 最新数据是 {latest_date}"
    return True, f"数据新鲜: 最新数据是 {latest_date}"

def check_database_size():
    """检查数据库大小"""
    db_size = Path('data/stock_data.db').stat().st_size
    db_size_mb = db_size / 1024 / 1024
    
    if db_size_mb > 1000:  # 1GB
        return False, f"数据库过大: {db_size_mb:.0f}MB"
    return True, f"数据库大小正常: {db_size_mb:.0f}MB"

def check_disk_space():
    """检查磁盘空间"""
    import shutil
    stat = shutil.disk_usage('.')
    free_percent = stat.free / stat.total * 100
    
    if free_percent < 10:
        return False, f"磁盘空间不足: 仅剩 {free_percent:.1f}%"
    return True, f"磁盘空间充足: {free_percent:.1f}%"

if __name__ == '__main__':
    checks = [
        check_data_freshness(),
        check_database_size(),
        check_disk_space(),
    ]
    
    for ok, msg in checks:
        status = "✓" if ok else "✗"
        print(f"{status} {msg}")
```

### 5.2 告警规则

| 指标 | 阈值 | 级别 | 响应 |
|------|------|------|------|
| 数据延迟 | > 24小时 | P0 | 立即修复 |
| 磁盘空间 | < 10% | P1 | 2小时内清理 |
| 数据库大小 | > 1GB | P2 | 24小时内优化 |
| 筛选器失败 | 连续3次 | P1 | 检查修复 |
| Dashboard响应 | > 5秒 | P2 | 性能优化 |

---

## 6. 附录

### 6.1 重要文件路径

| 类型 | 路径 | 说明 |
|------|------|------|
| 主数据库 | `data/stock_data.db` | 核心数据文件 |
| 进度文件 | `data/daily_update_progress_v2.json` | 每日更新进度 |
| Dashboard | `dashboard/app.py` | Web服务入口 |
| 日志目录 | `logs/` | 所有日志文件 |
| 备份目录 | `~/Backups/neo/` | 异地备份 |

### 6.2 常用命令速查

```bash
# 启动Dashboard
python3 dashboard/app.py

# 运行数据更新
python3 scripts/daily_update_screener.py --loop

# 运行所有筛选器
python3 scripts/run_all_screeners.py --date $(date +%Y-%m-%d)

# 检查数据库
sqlite3 data/stock_data.db ".tables"
sqlite3 data/stock_data.db "SELECT COUNT(*) FROM daily_prices;"
sqlite3 data/stock_data.db "PRAGMA integrity_check;"

# 查看日志
tail -f logs/dashboard.log
tail -f logs/daily_update_$(date +%Y%m%d).log

# 备份
cp data/stock_data.db data/stock_data.db.bak.$(date +%Y%m%d)
```

### 6.3 相关文档

- [数据管道文档](./data_pipeline.md)
- [筛选器使用指南](./screener_guide.md)
- [API文档](./api_reference.md)
