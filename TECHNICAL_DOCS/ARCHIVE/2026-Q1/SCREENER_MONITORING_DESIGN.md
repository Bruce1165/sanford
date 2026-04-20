# Screener Pick Monitoring System - Design Document

**Status:** Phase 1 In Progress
**Created:** 2026-03-21
**Updated:** 2026-03-21
**Author:** Neo

---

## 1. Concept Overview

A **visual pipeline** showing screener picks progressing through days, falling off when conditions break.

```
Coffee Cup Pipeline — 25 Day Tracking (Long-term Pattern)

Day 0    Day 1-5    Day 6-15    Day 16-24    Day 25 (Graduated)
(新进)   (早期)      (中期)       (后期)       (毕业)
┌─────┐  ┌─────┐    ┌─────┐     ┌─────┐      ┌─────┐
│NEW  │→ │ ✓   │ →  │ ✓   │  →  │ ✓   │  →   │ ★   │
│A    │  │     │    │     │     │     │      │     │
│B    │  │ ✓   │ →  │ ✓   │  →  │ ✗   │      │     │
│     │  │     │    │     │     │(失败)│      │     │
│C    │  │ ✓   │ →  │ ✗   │                          
│     │  │     │    │(失败)│                          
└─────┘  └─────┘    └─────┘     └─────┘      └─────┘
  5只     4 active    3 active    2 active       1 graduated

Pipeline Groups:
- NEW: 今天新进 (Day 0)
- EARLY: 早期跟踪 (Day 1-5)
- MID: 中期跟踪 (Day 6-15)
- LATE: 后期跟踪 (Day 16-24)
- GRADUATED: 完成 25 天 (成功毕业)
- FAILED: 已失败 (但继续显示直到毕业日)

Note: Failed stocks (✗) remain visible in pipeline until Day 25
```

### Key Principles
- **Automatic entry:** All screener picks enter monitoring immediately
- **Per-screener tracking:** Each screener has its own pipeline
- **Manual verification (Phase 1):** Human reviews daily, marks pass/fail
- **Automated rules (Phase 2):** Conditions coded, auto-mark failures
- **Exit outcomes:** `graduated` (reached Day 25) or `failed` (conditions broke, but continues tracking)

---

## 2. Database Schema

```sql
-- New table: screener_picks
CREATE TABLE screener_picks (
    id INTEGER PRIMARY KEY,
    screener_id TEXT,              -- 'coffee_cup_screener'
    stock_code TEXT,
    entry_date TEXT,               -- Day 0 (pick date)
    entry_price REAL,              -- Day 0 closing price
    expected_exit_date TEXT,       -- Day 10 (10th trading day)

    status TEXT,                   -- 'active', 'graduated', 'failed'
    exit_date TEXT,                -- when marked graduated/failed
    exit_reason TEXT,              -- 'completed' or 'failed_day_3'

    -- Daily tracking (JSON array of day checks)
    daily_checks TEXT,             -- '[{"day":1,"date":"2026-03-22","status":"pass","note":""}, ...]'

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX idx_picks_screener_date ON screener_picks(screener_id, entry_date);
CREATE INDEX idx_picks_status ON screener_picks(status);

-- Note: Duplicate prevention logic
-- If (screener_id, stock_code) pair already has an 'active' pick,
-- do NOT create a new entry when the same stock is picked again.
-- The existing track continues from its original Day 0.
```

---

## 3. Backend Logic

### Daily Batch Job (runs after data download)

1. Query all `active` picks where `expected_exit_date >= today`
2. For each pick:
   - Check if stock has data for today
   - If no data → skip (holiday/weekend handling)
   - If data exists → prepare for review (Phase 1) or check conditions (Phase 2)
3. Update `daily_checks` JSON
4. If conditions fail → mark `status='failed'`, set `exit_date`, `exit_reason`
5. If today == `expected_exit_date` and still active → mark `status='graduated'`

### Phase 1 (Manual Review)

- Daily job generates "to-review" list
- User marks pass/fail via UI
- Conditions tracked in notes for later automation

### Phase 2 (Automated)

- Rules engine evaluates conditions per screener
- Auto-mark failures based on price action, volume, etc.

---

## 4. Frontend - Pipeline View

### New Tab: "Monitor"

```
┌─────────────────────────────────────────────────────────────────┐
│  Coffee Cup Pipeline                            [? Help]        │
├─────────────────────────────────────────────────────────────────┤
│  Active Picks: 12    Graduated: 45    Failed: 23    Win Rate: 66%│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Day 0 (Today-10)   Day 1      Day 2      Day 3      Day 4-10   │
│  ┌─────────┐       ┌────────┐  ┌────────┐  ┌────────┐           │
│  │ 600519  │   →   │ ✓      │→ │ ✓      │→ │ ✓      │ → ...    │
│  │ 茅台    │       │ 3/21   │  │ 3/24   │  │ 3/25   │           │
│  │ ¥168.50 │       │ ¥172   │  │ ¥171   │  │ ¥175   │           │
│  └─────────┘       └────────┘  └────────┘  └────────┘           │
│                                                                 │
│  ┌─────────┐       ┌────────┐  ┌────────┐                       │
│  │ 000001  │   →   │ ✓      │→ │ ✗      │→ │ ✗      │          │
│  │ 平安银行│       │ 3/21   │  │ 3/24   │  │ 3/25   │           │
│  │ ¥12.50  │       │ ¥12.80 │  │ ¥12.20 │                       │
│  └─────────┘       └────────┘  └────────┘  └────────┘           │
│                                                                 │
│  [Check Today's Active Picks →]  (opens daily review modal)     │
└─────────────────────────────────────────────────────────────────┘
```

### Daily Review Modal

- Shows stock chart (K-line from entry to today)
- Entry conditions displayed for reference
- Notes field for failure reason ("Broke cup rim", "Volume dried up")
- Pass/Fail buttons

---

## 5. Daily Review Workflow (Phase 1)

### 17:30 Daily Notification (Cron Job)

```
Today's Monitoring Tasks - 8 picks to review

Coffee Cup (3 picks):
- 600519: Current ¥175 (Entry ¥168.50, +3.9%) - [✓ Pass] [✗ Fail]
- 000001: Current ¥12.20 (Entry ¥12.50, -2.4%) - [✓ Pass] [✗ Fail]
- 002415: Current ¥89 (Entry ¥85, +4.7%) - [✓ Pass] [✗ Fail]

Daily Hot (5 picks):
...
```

---

## 6. Stats & Analytics

Track per-screener:
- **Win rate** (graduated / total picks)
- **Average hold time** (when do most failures happen?)
- **Average gain/loss** (entry vs exit price)
- **Pipeline velocity** (how many make it to Day 3, Day 5, Day 8)

---

## 7. Implementation Phases

| Phase | Status | Tasks |
|-------|--------|-------|
| **Phase 1: Foundation** | ✅ Complete | Database schema, `ScreenerMonitor` class, auto-create picks via `base_screener.py` |
| **Phase 2: Pipeline UI** | ⏳ Pending | New "Monitor" tab, visual pipeline display (NEW→EARLY→MID→LATE→GRADUATED), basic stats |
| **Phase 3: Daily Workflow** | ✅ Complete | Daily cron job at 17:30, automatic evaluation, Pass/Fail/Graduate logic |
| **Phase 4: Analytics** | ⏳ Pending | Win rate tracking, performance charts, per-screener statistics |

---

## 8. Specifications (Confirmed)

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Monitoring duration** | Screener-specific | Coffee Cup: **25 trading days** (long-term pattern) |
| **Day counting** | Trading days | Day 1 = Friday → Day 2 = Monday (skips weekends/holidays) |
| **Duplicate handling** | Continue existing track | If stock re-picked while already monitoring, don't create duplicate entry |
| **Failure behavior** | Keep showing as failed | Failed stocks remain visible in pipeline (marked ✗), tracking continues until exit day |
| **Entry price** | Day 0 closing price | Price at which stock was picked |
| **Multi-screener** | Independent tracking | Same stock picked by different screeners = separate candidates |
| **Evaluation logic** | Fail-only | Only define failure conditions; no failure = continue tracking |
| **Pipeline view** | Required | Show: New (Day 0) → Tracking (Day 1-24) → Graduated/Failed |

---

## 10. Daily Automation Workflow

### **收盘后全自动流程**

```
15:30  数据下载编排器启动 (cron)
  ├─ 下载 iFind Realtime 数据 (4663只股票)
  ├─ 验证数据完整性
  ├─ 回填缺失数据 (如有)
  └─ 运行全部14个筛选器
      └─ 新picks自动进入监控

17:00  数据健康检查 (cron)
  └─ 验证当日数据完整性

17:30  筛选器监控评估 (cron)
  └─ 自动评估所有活跃picks
      ├─ Coffee Cup: 检查失败线/提前成功
      └─ 其他: 待定义
```

### **用户操作**

**无需手动操作！** 每日收盘后系统自动完成：
1. 数据下载
2. 运行所有筛选器
3. 评估已有picks

**用户只需：**
- 打开 Dashboard 查看最新筛选结果
- 查看 Monitor 页面了解跟踪状态

### **周一首次运行**

- **15:30**: 下载上周五数据 (2026-03-20)，运行筛选器
- **17:30**: 评估已有picks (包括之前创建的)

---

## 11. Files Status

### New Files
- `scripts/screener_monitor.py` - ✅ Core monitoring logic
- `scripts/daily_screener_monitor.py` - ✅ Daily automatic evaluation
- `scripts/run_all_screeners.py` - ✅ Batch run all 14 screeners
- `database/migrations/007_add_screener_picks.sql` - ✅ Schema migration
- `database/migrations/008_add_cup_pattern_fields.sql` - ✅ Cup pattern fields
- `dashboard2/frontend/src/components/Monitor/` - ⏳ Pending
- `dashboard2/frontend/src/pages/Monitor.tsx` - ⏳ Pending

### Modified Files
- `scripts/base_screener.py` - ✅ Auto-create picks with cup pattern data
- `scripts/download_orchestrator.py` - ✅ Added step4 to run all screeners
- `dashboard2/frontend/src/App.tsx` - ⏳ Pending
- `dashboard2/backend/app.py` - ⏳ Pending

---

*Document Status: Phase 1 & 3 Complete. Phase 2 (UI) pending.*
