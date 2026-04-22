# NeoTrade2 项目状态记录

**最后更新时间**: 2026-04-13

---

## ✅ 已完成的修改

### 前端
- **文件**: `frontend/src/App.tsx`
- **修改内容**:
  1. 添加 `checkDate` 状态变量（默认为当天）
  2. 添加 `showCheckCalendar` 状态变量
  3. 修改 `handleCheck` 函数使用 `checkDate` 参数
  4. 添加 `CalendarWithButton` 组件到 Check Stock 区域
  5. 添加 `useEffect` 监听器，筛选器变化时重置状态

- **文件**: `frontend/src/cockpit.css`
- **添加内容**: `.sl-check-input-with-calendar` 样式

### 后端
- **文件**: `backend/app.py`
- **修改内容**:
  1. 删除第一处 `shi_pan_xian_screener` 特殊处理（line 845-862，尝试导入不存在的 lite 模块）
  2. 删除第二处特殊处理（line 878-901，直接返回 mock 结果）
  3. 添加公开 API 端点列表：`['/api/health', '/api/check-stock']`

---

## 📊 当前服务状态

### 后端
- **端口**: 8765
- **状态**: 运行中
- **健康检查**: `http://localhost:8765/api/health` ✅ 正常

### 前端
- **端口**: 3000 (Vite dev server)
- **状态**: 运行中

---

## 📋 筛选器状态变更

### 已禁用的筛选器
以下筛选器已禁用，不再在 Dashboard 中显示：

1. **咖啡杯形态筛选器** (`coffee_cup_screener`)
   - 禁用日期: 2026-04-13
   - 原因: 已被 `coffee_cup_handle_screener_v4`（咖啡杯V4）替代
   - 状态: ❌ 禁用（数据库 enabled=0）

2. **杯柄筛选器** (`cup_handle_screener`)
   - 禁用日期: 2026-04-13
   - 原因: 已被 `coffee_cup_handle_screener_v4`（咖啡杯V4）替代
   - 状态: ❌ 禁用（数据库 enabled=0）

### 推荐使用的替代筛选器
- **咖啡杯V4** (`coffee_cup_handle_screener_v4`)
  - 功能: 完整的咖啡杯柄形态筛选，支持 Check 功能
  - 状态: ✅ 活跃（数据库 enabled=1）
  - 优势: 更精确的形态识别，支持单个股票检查

### 实施的变更
1. ✅ 数据库添加 `enabled` 字段（默认值为 1）
2. ✅ 禁用 `coffee_cup_screener` 和 `cup_handle_screener`
3. ✅ 修改 `backend/models.py` 中的 `get_all_screeners()` 函数，只返回 enabled=1 的筛选器
4. ✅ Flask 服务已重启，变更已生效
5. ✅ 验证：API 只返回 14 个筛选器（不包括已禁用的 2 个）

### 如何重新启用
如需重新启用已禁用的筛选器：
```sql
UPDATE screeners SET enabled = 1 WHERE name = 'coffee_cup_screener';
```

---

## ⚠️ 待解决的问题

### 涨停试盘线筛选器错误
**错误信息**:
```
"name 'module_name' is not defined"
```

**问题分析**:
- 错误发生在 `screeners/shi_pan_xian_screener.py` 的 `check_single_stock` 方法
- 第 309-311 行使用 `info['name']` 访问字典
- `_get_stock_info` 方法返回的字典结构可能有问题，使用了单数形式键（`name`, `cap`）而不是字典形式

**可能原因**:
1. Python 模块缓存问题导致修改未生效
2. 文件中存在重复代码（第 309-313 行和第 310-315 行）

**尝试的修复**:
1. 使用 Python 脚本直接修改第 309-311 行
2. 使用 regex 查找所有 `info['name']` 出现位置并替换

---

## 📝 已测试功能

### 日期选择器
- ✅ Calendar 组件已添加到 Check Stock 区域
- ✅ 日历按钮可以点击
- ✅ 默认日期为当天（`YYYY-MM-DD` 格式）

### 筛选器重置逻辑
- ✅ 筛选器变化时，旧结果会被清除
- ✅ loading 状态会被重置

---

## 🔄 待测试

1. 测试涨停试盘线筛选器是否能正常加载和运行
2. 验证日期选择器在所有筛选器中都能正常工作
3. 确认前端和后端的日期参数传递正确

---

**说明**: 
- 8765 端口是测试环境的旧版本
- 生产环境可能需要使用不同的端口
- 建议清理 Python 进程缓存后重启
