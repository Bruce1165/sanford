# 筛选器禁用记录

**日期：** 2026-04-13
**版本：** v1.0
**类型：** 配置变更

---

## 📋 变更概述

本次变更禁用了两个旧版本的咖啡杯筛选器，统一使用 `coffee_cup_handle_screener_v4`（咖啡杯V4）作为替代方案。

### 变更原因
1. **功能重复**：`coffee_cup_screener` 和 `cup_handle_screener` 的功能已被 V4 版本完全覆盖
2. **维护成本**：维护多个功能相似的筛选器增加了代码复杂度
3. **功能优势**：V4 版本支持单个股票检查功能（Check Stock），功能更完整

---

## 🗑️ 已禁用的筛选器

### 1. coffee_cup_screener（咖啡杯形态筛选器）

| 属性 | 值 |
|------|---|
| **数据库ID** | 133 |
| **名称** | `coffee_cup_screener` |
| **显示名称** | 咖啡杯形态筛选器 |
| **文件路径** | `screeners/coffee_cup_screener.py` |
| **配置文件** | `config/screeners/coffee_cup.json` |
| **禁用日期** | 2026-04-13 |
| **禁用状态** | enabled = 0 |
| **替代方案** | coffee_cup_handle_screener_v4 |

**功能特点（旧）：**
- 杯体 50-60天，杯深 12%-35%
- 柄部 15-20天，回调 5%-12%
- U型验证（最低点 30%-70% 中部）
- 均线多头排列 (50/150/200)
- RS ≥ 85
- ❌ 不支持单个股票检查功能

---

### 2. cup_handle_screener（杯柄筛选器）

| 属性 | 值 |
|------|---|
| **数据库ID** | 142 |
| **名称** | `cup_handle_screener` |
| **显示名称** | 杯柄筛选器 |
| **文件路径** | `screeners/cup_handle_screener.py` |
| **配置文件** | `config/screeners/cup_handle.json` |
| **禁用日期** | 2026-04-13 |
| **禁用状态** | enabled = 0 |
| **替代方案** | coffee_cup_handle_screener_v4 |

---

## ✅ 推荐使用的替代筛选器

### coffee_cup_handle_screener_v4（咖啡杯V4）

| 属性 | 值 |
|------|---|
| **数据库ID** | 143 |
| **名称** | `coffee_cup_handle_screener_v4` |
| **显示名称** | 咖啡杯V4 |
| **文件路径** | `screeners/coffee_cup_handle_screener_v4.py` |
| **配置文件** | `config/screeners/coffee_cup_v4.json` |
| **启用状态** | enabled = 1 ✅ |

**功能特点（新）：**
- 两个杯沿高点统一处理，间隔 45-250天
- 杯柄：右侧杯沿后 0-13天的走势
- 杯柄可上扬、平拉、下跌（但下跌≤杯深/2）
- 温和上涨细分为震荡期和快速上涨期
- 成交量条件：右侧杯沿前N天平均 ≥ 左侧杯沿后N天平均 × 1倍
- **✅ 支持单个股票检查功能（Check Stock）**
- **✅ 26个可调节参数**
- **✅ 支持动态回溯天数计算**

---

## 🔧 技术实施

### 1. 数据库 Schema 变更

**添加字段：**
```sql
ALTER TABLE screeners ADD COLUMN enabled INTEGER DEFAULT 1;
```

**字段说明：**
- `enabled` (INTEGER): 筛选器启用状态
  - `1` = 启用（在 Dashboard 中显示）
  - `0` = 禁用（不在 Dashboard 中显示）

### 2. 数据变更

**禁用筛选器：**
```sql
UPDATE screeners SET enabled = 0
WHERE name IN ('coffee_cup_screener', 'cup_handle_screener');
```

**验证结果：**
```sql
SELECT id, name, display_name, enabled FROM screeners
WHERE name IN ('coffee_cup_screener', 'cup_handle_screener', 'coffee_cup_handle_screener_v4');
```

输出：
```
133|coffee_cup_screener|咖啡杯形态筛选器|0
142|cup_handle_screener|杯柄筛选器|0
143|coffee_cup_handle_screener_v4|咖啡杯V4|1
```

### 3. 后端代码变更

**文件：** `backend/models.py`

**函数：** `get_all_screeners()`

**变更前：**
```python
def get_all_screeners():
    """Get all registered screeners"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM screeners ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

**变更后：**
```python
def get_all_screeners():
    """Get all registered screeners (only enabled ones)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM screeners WHERE enabled = 1 ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

### 4. 前端变更

**无需修改：** 前端通过 `/api/screeners` 端点获取筛选器列表，后端已自动过滤掉禁用的筛选器。

### 5. 服务重启

```bash
# 停止 Flask 服务
lsof -i :8765 | grep LISTEN | awk '{print $2}' | xargs kill -9

# 启动 Flask 服务
cd backend
python3 app.py --port 8765
```

---

## ✅ 验证结果

### API 测试

**请求：**
```bash
curl -s http://localhost:8765/api/screeners | python3 -m json.tool
```

**结果：**
- 返回的筛选器总数：**14 个**
- 不包含已禁用的 `coffee_cup_screener` 和 `cup_handle_screener`
- 包含启用的 `coffee_cup_handle_screener_v4`

**验证命令：**
```bash
curl -s http://localhost:8765/api/screeners | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Total active screeners: {len(data[\"screeners\"])}')
coffee_screeners = [s for s in data['screeners'] if 'coffee' in s['name'] or 'cup' in s['name']]
for s in coffee_screeners:
    print(f'  - {s[\"name\"]} ({s[\"display_name\"]})')
"
```

**输出：**
```
Total active screeners: 14
  - coffee_cup_handle_screener_v4 (咖啡杯V4)
```

### 前端验证

1. 访问 http://localhost:8765
2. 筛选器列表中只显示 **"咖啡杯V4"**
3. 不再显示 **"咖啡杯形态筛选器"** 和 **"杯柄筛选器"**

### Check 功能测试

**请求：**
```bash
curl -s -X POST "http://localhost:8765/api/check-stock" \
  -H "Content-Type: application/json" \
  -d '{"code":"300033","screener":"coffee_cup_handle_screener_v4","date":"2026-04-13"}' \
  | python3 -m json.tool | head -20
```

**结果：**
```json
{
  "code": "300033",
  "name": "同花顺",
  "date": "2026-04-13",
  "match": false,
  "reasons": ["未找到咖啡杯V4形态..."],
  "details": null
}
```

---

## 📝 如何重新启用

### 场景1：重新启用单个筛选器

```sql
-- 启用咖啡杯形态筛选器
UPDATE screeners SET enabled = 1 WHERE name = 'coffee_cup_screener';
```

### 场景2：批量启用

```sql
-- 同时启用多个筛选器
UPDATE screeners SET enabled = 1
WHERE name IN ('coffee_cup_screener', 'cup_handle_screener');
```

### 场景3：查看所有筛选器状态

```sql
-- 查看所有筛选器及其启用状态
SELECT
  id,
  name,
  display_name,
  CASE WHEN enabled = 1 THEN '✅ 启用' ELSE '❌ 禁用' END as status,
  created_at,
  updated_at
FROM screeners
ORDER BY name;
```

### 场景4：只查看已禁用的筛选器

```sql
-- 查看已禁用的筛选器
SELECT
  id,
  name,
  display_name,
  updated_at
FROM screeners
WHERE enabled = 0
ORDER BY updated_at DESC;
```

---

## 📊 影响范围

### 影响的用户行为

| 用户行为 | 变更前 | 变更后 |
|---------|--------|--------|
| Dashboard 筛选器列表 | 显示 16 个筛选器 | 显示 14 个筛选器 |
| 咖啡杯形态筛选 | 可选择 3 个咖啡杯相关筛选器 | 只能选择 1 个（V4） |
| Check 功能 | 可用筛选器较少 | 可用筛选器更多（V4 支持 Check） |
| 筛选器参数配置 | 需要配置 3 个筛选器 | 只需配置 1 个筛选器 |

### 不受影响的功能

- ✅ 数据下载和更新
- ✅ 其他 12 个筛选器的运行
- ✅ 历史数据回测
- ✅ 监控和报警
- ✅ 用户认证和权限管理

---

## 🔄 回滚方案

如果需要回滚此次变更：

### 方案1：重新启用筛选器

```sql
UPDATE screeners SET enabled = 1
WHERE name IN ('coffee_cup_screener', 'cup_handle_screener');
```

### 方案2：删除 enabled 字段

```sql
-- 1. 备份数据库
cp data/dashboard.db data/dashboard.db.backup_20260413

-- 2. 创建新表（不含 enabled 字段）
CREATE TABLE screeners_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,
    file_path TEXT NOT NULL,
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 迁移数据
INSERT INTO screeners_new (id, name, display_name, description, file_path, config, created_at, updated_at)
SELECT id, name, display_name, description, file_path, config, created_at, updated_at
FROM screeners;

-- 4. 替换表
DROP TABLE screeners;
ALTER TABLE screeners_new RENAME TO screeners;
```

---

## 📚 相关文档

- [09_SCREENERS_GUIDE.md](09_SCREENERS_GUIDE.md) - 筛选器汇总和管理指南
- [11_COFFEE_CUP_PARAMS_V4.md](11_COFFEE_CUP_PARAMS_V4.md) - 咖啡杯V4参数详解
- [15_SCREENER_MANAGEMENT.md](15_SCREENER_MANAGEMENT.md) - 筛选器管理指南

---

## 📅 变更日志

| 日期 | 版本 | 变更内容 | 变更人 |
|------|------|----------|--------|
| 2026-04-13 | v1.0 | 禁用 coffee_cup_screener 和 cup_handle_screener | Claude |

---

**文档版本：** v1.0
**最后更新：** 2026-04-13
**维护者：** NeoTrade2 技术团队
