# 老鸭头多轮筛选系统实施拆解（V1.0）

> 版本：V1.0  
> 状态：已冻结（按已确认决策执行）  
> 更新时间：2026-04-22

## 1. 已冻结范围

1. 去重主键：`stock_code + selector_id + select_date + snapshot_id`
2. 新增业务幂等键：`pool_biz_key`
3. `failed_stocks` 仅统计执行失败（不含 `not_selected`）
4. 失败码字典：`DATA_MISSING/DATA_INVALID/SUSPENDED/TIMEOUT/CHECK_EXCEPTION/DB_WRITE_ERROR/DEPENDENCY_FAILED/CIRCUIT_BREAKER_STOP`
5. 上传默认增量追加；支持 `强制覆盖`（清空股票池后以文件重建）
6. 文件名日期为唯一权威
7. 上传后触发策略：仅入队，由调度器串行执行
8. Dashboard 改造边界：仅 `right-zone`

## 2. 交付目标

1. 实现多轮筛选流程（支持 DAG 配置、并行/串行节点）
2. 实现上传驱动的数据更新与任务队列
3. 实现结果快照切换与秒级回滚
4. 实现可追踪日志、失败归因、性能指标
5. 在 `right-zone` 提供时间轴、穿透查询、热力图、回测与 AB 对比能力

## 3. 文件级任务拆解

### P0 数据口径与一致性（先做）

1. `scripts/database/migrations/create_lao_ya_tou_pool_table.sql`
   - 增加 `pool_biz_key` 字段与唯一索引
   - 增加必要索引（`processed`, `stock_code`, `start_date/end_date`）
2. `scripts/database/migrations/create_lao_ya_tou_five_flags.sql`
   - 明确 `snapshot_id`、`selector_id`（或兼容 `screener_id`）字段
   - 将唯一约束切换为四键：`stock_code, selector_id, select_date, snapshot_id`
3. `scripts/database/migrations/add_unique_constraint_five_flags_v3.sql`
   - 新增 V1.0 迁移脚本，避免继续沿用旧三键约束
4. `scripts/database/lao_ya_tou_five_flags.py`
   - 修复单条/批量插入参数数量与字段顺序不一致问题
   - 引入失败码字段写入接口（为日志表准备）
5. `scripts/run_five_flags_pool_screening.py`
   - 修正 `failed_stocks` 统计口径（失败不等于未命中）
   - 引入 `run_id/snapshot_id` 透传
6. `backend/app.py`
   - 修正 `/api/five-flags/results` 的 `dedupe_key` 输出，与冻结规则一致

### P1 上传与调度链路

1. `backend/app.py`
   - 新增上传接口（含 `force_overwrite`）
   - 新增上传任务状态查询接口
   - 新增入队接口或内部服务调用
2. `backend/excel_upload.py`
   - 文件名规则解析：`老鸭头YYMMDD.xlsx` 与 `老鸭头YYMMDD-YYMMDD.xlsx`
   - 日期以文件名为准，内容日期冲突时阻断并记录
3. `scripts/database/lao_ya_tou_pool.py`
   - 支持默认增量 upsert（按 `pool_biz_key`）
   - 支持强制覆盖（全量删除后重建）
4. `data/five_flags_runs.json`（运行时文件）
   - 保持兼容读取，逐步过渡到标准 `screening_run` 表
5. `scripts/cron/five_flags_pool_task.py`
   - 改为队列消费入口，串行调度

### P2 DAG 与多轮执行

1. `scripts/run_five_flags_pool_screening.py`
   - 抽象成通用 Flow Runner（节点批次执行）
   - 支持并行节点、依赖校验、失败短路
2. `scripts/pool_screener_adapter.py`
   - 统一 selector/check 输出协议与错误映射
3. 新增 `scripts/flow_engine/*.py`
   - DAG 配置加载、拓扑排序、执行器与状态持久化
4. `backend/app.py`
   - 新增 flow 管理与 run 详情 API

### P3 Dashboard right-zone 可视化

1. `frontend/src/pages/FiveFlagsMonitor.tsx`
   - 在 `right-zone` 增加时间轴、热力图、回测、AB 对比面板
   - 保持页面外框与非 right-zone 区域不变
2. 新增 `frontend/src/api/five-flags.ts`
   - 封装 timeline/heatmap/backtest/ab API
3. 新增 `frontend/src/types/five-flags.ts`
   - 增加运行态、失败码、快照、热力图数据类型

### P4 测试与验收

1. `tests/test_lao_ya_tou_five_flags.py`
   - 增加四键去重与失败码落库测试
2. `tests/test_run_five_flags_pool_screening.py`
   - 修正与当前实现不一致的旧断言
   - 新增失败口径与 run/snapshot 透传测试
3. `tests/test_five_flags_cron_task.py`
   - 增加上传入队与串行调度测试
4. 新增 `tests/test_five_flags_upload_pipeline.py`
   - 覆盖增量与强制覆盖两条链路

## 4. 实施顺序（严格执行）

1. P0：口径与数据一致性（不可跳过）
2. P1：上传与调度链路
3. P2：DAG 多轮执行
4. P3：right-zone 可视化
5. P4：测试补齐与验收

## 5. 完成标准（DoD）

1. 代码层：核心接口可运行，关键路径无语法错误
2. 数据层：去重键、失败口径、快照读写一致
3. 业务层：上传后可自动入队并处理 `processed=0`
4. 可视化层：`right-zone` 四类视图可用
5. 运维层：切换门禁与回滚可演练
