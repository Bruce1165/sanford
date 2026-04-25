# 老鸭头五图 P1 联调手册（用户需求视角）

> 目标：你可以直接验证“上传文件后自动入队、串行执行、可查状态”是否满足业务预期。  
> 适用范围：`P1` 已实现接口。

## 1. 你现在能直接验证的需求

1. 上传老鸭头文件后，不会并发乱跑，而是进入串行队列。
2. 默认增量追加；可勾选 `force_overwrite=true` 做“清空后重建”。
3. 上传后可拿到 `job_id`，并持续查询任务状态。
4. 手动触发和失败重试也都走同一串行队列。

## 2. 联调前准备

1. 后端服务已启动（默认 `http://127.0.0.1:8765`）。
2. 文件名必须是以下之一：
   - `老鸭头YYMMDD.xlsx`
   - `老鸭头YYMMDD-YYMMDD.xlsx`
3. 表头至少包含：
   - `股票代码`
   - `股票名称`

## 3. 场景 A：上传并自动入队

### 请求

```bash
curl -u :$DASHBOARD_PASSWORD \
  -X POST "http://127.0.0.1:8765/api/five-flags/pools/upload" \
  -F "file=@/absolute/path/老鸭头260422.xlsx" \
  -F "force_overwrite=false"
```

### 你应看到的关键返回

```json
{
  "success": true,
  "upload": {
    "status": "success",
    "mode": "incremental",
    "message": "增量导入成功：新增 120 条，跳过重复 15 条"
  },
  "queue": {
    "job_id": "ffq_20260422_123456_abcd1234",
    "status": "queued",
    "run_id": null
  }
}
```

说明：
1. `job_id` 是后续查询状态的唯一键。
2. `status=queued` 表示已入队，等待串行调度。
3. 若当时无活跃任务，可能直接返回 `status=accepted` 并给出 `run_id`。

## 4. 场景 B：查询上传任务状态

### 请求（推荐）

```bash
curl -u :$DASHBOARD_PASSWORD \
  "http://127.0.0.1:8765/api/five-flags/pools/upload-status/ffq_20260422_123456_abcd1234"
```

### 你应关注的字段

1. `job.status`：
   - `queued`：排队中
   - `started`：已启动运行
   - `completed`：运行完成
   - `failed`：运行失败
2. `job.run_id`：已启动后会有值，可用于看 run 明细。
3. DAG 观测字段（任务启动后）：
   - `job.flow_id`
   - `job.flow_plan_type`（`dag` 或 `batches`）
   - `job.total_levels`
   - `job.current_level`（示例：`{"index":2,"total":3,"screeners":["zhang_ting_bei_liang_yin"]}`）
   - `job.level_duration_ms`（示例：`{"1": 832.41, "2": 420.17, "3": 615.03}`，单位毫秒）

## 5. 场景 C：手动触发（同样入队）

### 请求

```bash
curl -u :$DASHBOARD_PASSWORD \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:8765/api/five-flags/run" \
  -d '{"pool_ids":[101,102], "max_workers":4, "flow_config":"scripts/flow_engine/default_five_flags_dag.json", "market_phase":"WAVE_3", "phase_profile":"config/screeners/market_phase_profiles.json", "profile_slot":"candidate", "calibration_note":"W3 灵敏度第2轮"}'
```

### 返回关键

```json
{
  "job_id": "ffq_20260422_130000_ef901234",
  "status": "queued",
  "queue_status": "queued",
  "accepted": false,
  "run_id": null,
  "queued_pools": 2
}
```

## 6. 场景 D：失败重试（同样入队）

### 请求

```bash
curl -u :$DASHBOARD_PASSWORD \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:8765/api/five-flags/retry-failed" \
  -d '{"pool_ids":[101,102], "run_id":"ffrun_20260422_120000_xxxx", "market_phase":"WAVE_B", "profile_slot":"active"}'
```

## 7. 场景 E：查看全队列

### 请求

```bash
curl -u :$DASHBOARD_PASSWORD \
  "http://127.0.0.1:8765/api/five-flags/queue?limit=20"
```

### 你能得到什么

1. 当前排队、执行中、已完成、失败数量统计。
2. 最近任务列表，可快速确认“是否串行执行”。
3. 运行中任务可观察 DAG 实时层级（`flow_id/current_level`）。
4. 运行中和完成后都可看到各层累计耗时（`level_duration_ms`）。
5. 运行中和完成后可观察本次市场阶段参数快照（`market_phase/phase_param_profile`）。
6. 可追踪本次参数槽位和校准备注（`profile_slot/profile_version/calibration_note`）。

## 8. 场景 F：查看最近多次层耗时对比（P2）

### 请求

```bash
curl -u :$DASHBOARD_PASSWORD \
  "http://127.0.0.1:8765/api/five-flags/flow/level-timing?limit_runs=20&spike_threshold=1.8"
```

可选参数：
1. `limit_runs`：统计最近多少次（默认 20，最大 100）。
2. `flow_id`：只看指定流程。
3. `spike_threshold`：抖动告警阈值（`max_ms/avg_ms`，默认 `1.8`，范围 `1.0~10.0`）。

### 你能得到什么

1. `summary.levels[].avg_ms/min_ms/max_ms`：每层耗时统计。
2. `summary.sampled_run_ids`：本次统计用了哪些 run。
3. `summary.slowest_level`：统计窗口内平均最慢层（含占比），可直接作为优化优先级。
4. `summary.levels[].spike_ratio/spike_alert`：识别偶发抖动（`max_ms/avg_ms >= spike_threshold` 且样本数≥3）。
5. `summary.spike_alert_levels`：有抖动风险的层编号列表。

## 9. 场景 G：发布 candidate 到 active（Calibration 发布）

### 请求

```bash
curl -u :$DASHBOARD_PASSWORD \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:8765/api/five-flags/phase-profile/publish" \
  -d '{"market_phase":"WAVE_3","from_slot":"candidate","to_slot":"active","calibration_note":"W3 第2轮验证通过","published_by":"team"}'
```

### 你能得到什么

1. 显式发布结果（`status=published`）。
2. 发布后的 `profile_version`。
3. 本次发布覆盖到的筛选器列表（`override_screeners`）。

## 10. 需求验收最短路径（建议）

1. 先上传一次增量文件，确认拿到 `job_id`。
2. 连续轮询上传状态接口，看到 `queued -> started -> completed`。
3. 在任务执行期间再触发一次手动 run，确认第二个任务保持 `queued`，不抢跑。
4. 再上传一次 `force_overwrite=true` 文件，确认模式与文案正确。

## 11. 常见失败与判定

1. 文件名不合规：直接 400，提示文件名格式错误。
2. 行内日期与文件名日期不一致：上传被阻断，不会入队。
3. 队列任务失败：`job.status=failed`，`job.error` 有错误信息。
4. 若 `run_id` 长时间为空：说明前面有任务占用串行窗口，属于预期行为。

## 12. P2 预备：可配置流程（已可用）

你现在可以在不改主代码的前提下，调整五图执行顺序。当前默认配置文件（DAG）：

`scripts/flow_engine/default_five_flags_dag.json`

如需继续使用批次模式，可手动指定：

`scripts/flow_engine/default_five_flags_flow.json`

示例：

```json
{
  "flow_id": "five_flags_default_v1",
  "batches": [
    ["er_ban_hui_tiao", "shi_pan_xian"],
    ["zhang_ting_bei_liang_yin"],
    ["jin_feng_huang", "yin_feng_huang"]
  ]
}
```

含义：
1. 同一 `batch` 内并行执行。
2. 不同 `batch` 按顺序执行。
3. 五个筛选器必须全部出现且不能重复。
4. 你也可以在 `/api/five-flags/run` 或 `/api/five-flags/retry-failed` 的请求体中传 `flow_config` 指定配置文件。
5. 8阶段参数策略可通过 `market_phase` 指定（`WAVE_1..WAVE_5/WAVE_A/WAVE_B/WAVE_C`）。
6. `phase_profile` 可指定策略文件；未命中阶段时自动回退 `default` 模板。
7. `profile_slot` 支持 `active/candidate`，`calibration_note` 用于记录本次校准意图。

## 13. 每日 17:00 自动运行与邮件简报

### 环境变量（Gmail）

```bash
export FIVE_FLAGS_DAILY_ENABLED=1
export FIVE_FLAGS_DAILY_TRIGGER_HOUR=17
export FIVE_FLAGS_DAILY_TRIGGER_MINUTE=0
export FIVE_FLAGS_EMAIL_TO="jin.bruce@gmail.com"
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT=465
export SMTP_USER="your_gmail@gmail.com"
export SMTP_PASSWORD="your_gmail_app_password"
```

### 行为说明

1. 到达 17:00 后，系统会自动入队一个 `daily_auto` 五图任务。
2. 任务开始时发送一封启动邮件。
3. 任务完成（`completed/failed`）后发送一封简报邮件。
4. 同一天只触发一次，触发状态保存在 `data/five_flags_daily_scheduler_state.json`。

### DAG 配置（P2）

你也可以使用 DAG 配置（节点依赖）：

`scripts/flow_engine/default_five_flags_dag.json`

示例：

```json
{
  "flow_id": "five_flags_dag_v1",
  "nodes": [
    {"id": "er_ban_hui_tiao", "depends_on": []},
    {"id": "shi_pan_xian", "depends_on": []},
    {"id": "zhang_ting_bei_liang_yin", "depends_on": ["er_ban_hui_tiao"]},
    {"id": "jin_feng_huang", "depends_on": ["zhang_ting_bei_liang_yin"]},
    {"id": "yin_feng_huang", "depends_on": ["shi_pan_xian", "zhang_ting_bei_liang_yin"]}
  ]
}
```

说明：
1. `depends_on` 为空表示可从第一层开始执行。
2. 引擎会自动做拓扑分层，同层并行、跨层串行。
3. 若出现环依赖，任务会在启动前直接报错并阻断执行。
