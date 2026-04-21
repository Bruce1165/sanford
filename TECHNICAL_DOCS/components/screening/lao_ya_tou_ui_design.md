# 老鸭头五图验证与门禁手册（v1）

> 版本：v1  
> 状态：生效中  
> 更新日期：2026-04-19

## 1. 目的

在进入五图 UI 开发前，先固化验证闭环，确保：

1. 双数据源运行一致
2. 参数调整后可复现
3. 结果落库无重复
4. 发布可验证、可回滚

## 2. 总体阶段

1. 阶段 A：冻结边界
2. 阶段 B：双数据源一致性验证
3. 阶段 C：CHECK 回放闭环验证
4. 阶段 D：发布门禁与回滚
5. 阶段 E：右侧五图 UI 最小闭环（仅在 A-D 全通过后执行）

## 3. 阶段 A（冻结边界）

### A.1 冻结区

1. `Data Health` 区域保持不变
2. 主布局与全局主题保持不变
3. 非五图页面不做结构性改造

### A.2 允许改动区

1. 五图 API
2. 五图脚本与数据层
3. 右侧五图展示组件（最小必要）

### A.3 执行要求

1. 每次改动前记录影响文件清单
2. 每次改动后记录可回滚点
3. 禁止大范围全局 CSS 变更

## 4. 阶段 B（双数据源一致性验证）

### B.1 验证对象

1. 数据源 A：股票数据库（全市场）
2. 数据源 B：老鸭头股票池数据库

### B.2 核查项

1. 参数来源一致（数据库优先/文件回退策略明确）
2. 参数快照版本一致
3. 五图筛选器集合一致
4. 输出字段结构一致
5. 日期窗口解释一致

### B.3 通过标准

1. 两条链路都可运行
2. 同一参数快照在两条链路都生效
3. 统计结果差异可解释

## 5. 阶段 C（CHECK 回放闭环验证）

### C.1 回放样本

1. 小样本：10 只股票
2. 中样本：50 只股票
3. 全量样本：当前未处理池

日期窗口建议：

1. 短窗：5-10 交易日
2. 中窗：20-30 交易日
3. 长窗：60+ 交易日

### C.2 必须验证的业务动作

1. 未处理日期枚举正确
2. CHECK 执行覆盖完整
3. 命中写入字段完整
4. `processed` 状态推进正确
5. 失败项可重试，不静默吞错

### C.3 去重规则（强制）

唯一重复定义：

1. `stock_code`
2. `screener_id`
3. `screen_date`

三者同时相同即重复，必须拦截。

### C.4 去重检查 SQL

```sql
SELECT stock_code, screener_id, screen_date, COUNT(*) AS cnt
FROM lao_ya_tou_five_flags
GROUP BY stock_code, screener_id, screen_date
HAVING COUNT(*) > 1;
```

### C.5 通过标准

1. 同批次重复运行新增记录为 0
2. 去重检查 SQL 返回空集
3. 抽样命中记录可追溯（票、筛选器、日期、理由）

## 6. 阶段 D（发布门禁与回滚）

### D.1 发布前门禁

1. Python 语法检查通过
2. 前端构建通过
3. `/api/health` 正常
4. 关键业务接口可用
5. 去重检查通过
6. 小样本回放冒烟通过

### D.2 快速回滚触发条件

1. 核心接口不可用
2. 重复写入出现
3. 状态推进错误
4. 参数快照生效异常

### D.3 回滚后校验

1. 健康检查通过
2. 关键接口恢复
3. 小样本回放恢复正常

## 7. 阶段 E（UI 最小闭环准入条件）

只有当 A-D 全通过后，才允许进入 UI 实现：

1. 仅改右侧五图区域
2. 不改 Data Health
3. 不改全局布局
4. UI 仅消费后端已验证结果，不承载筛选判定逻辑

## 8. 验证记录模板（每轮必须保存）

```text
批次ID:
参数快照ID:
执行人:
执行时间:
样本范围:
通过项:
失败项:
回滚是否触发:
备注:
```

## 9. 关联文档

1. 主线需求基线：`TECHNICAL_DOCS/components/screening/lao_ya_tou_five_flags_requirements.md`
2. 发布与回滚手册：`TECHNICAL_DOCS/reference/operations_guide.md`
3. 迭代记录与决策日志：`TECHNICAL_DOCS/system/05_project_management.md`
  - 黑色 (#000000)：主标题、内容
  - 灰色 (#888888)：次要说明
```

### 6.2 组件样式

```
Card 组件：
  - 圆角：8px
  - 阴影：0 2px 8px rgba(0,0,0,0.1)
  - 内边距：16px

Select 组件：
  - 高度：40px
  - 宽度：100%

Button 组件：
  - 主要按钮（蓝色）：padding 8px 16px
  - 次要按钮（灰色）：padding 8px 16px
  - 禁用状态：opacity 0.6, cursor not-allowed

Table 组件：
  - 表头：浅灰背景 (#fafafa)
  - 斑马线：边框分割
  - 行高：40px
  - 悬停：浅蓝背景 (#e6f7ff)
```

---

## 七、响应式设计

### 7.1 桌面端（> 1024px）
```
- 左侧面板：250px 固定宽度
- 右侧面板：剩余空间（flex: 1）
- 表格：显示完整信息
```

### 7.2 平板端（768px - 1024px）
```
- 左侧面板：220px 固定宽度
- 右侧面板：剩余空间
- 表格：精简列，隐藏"匹配原因"列
```

### 7.3 移动端（< 768px）
```
- 左侧面板：100% 宽度，堆叠在顶部
- 右侧面板：100% 宽度，堆叠在左侧下方
- 筛选器：水平滚动展示
```

---

## 八、性能优化

### 8.1 数据加载

```
- 首次加载：分页加载（每页 100 只）
- 滚动加载：无限滚动或"加载更多"按钮
- 缓存：股票列表缓存 5 分钟，减少重复请求
```

### 8.2 筛选优化

```
- 防抖：应用筛选按钮点击后 300ms 防抖
- 并发控制：筛选进行中时禁用按钮
- 进度显示：显示"已筛选 XX/YY 只股票"
```

---

## 九、Dashboard 集成

### 9.1 Dashboard 添加链接

```
在 MonitorV2 或 Dashboard 主页面添加：

```tsx
<Card title="快捷入口">
  <Button
    type="link"
    href="/five-flags"
    icon={<LineChartOutlined />}
  >
    老鸭头五旗选股池
  </Button>
</Card>
```

**位置：**
- Desktop：右侧边栏或首页快捷入口区
- Mobile：顶部导航栏"更多"菜单中

### 9.2 独立路由配置

```
frontend/src/App.tsx 添加：

```tsx
{
  path: '/five-flags',
  element: <LaoYaTouFiveFlags />
}
```

**注意：**
- 不依赖 Dashboard 的任何状态
- 独立的权限验证（可选）
- 独立的错误处理
```

---

## 十、实施计划

### 10.1 后端 API（Flask）

```python
# backend/app.py 添加路由

@app.route('/api/five-flags/stocks', methods=['GET'])
def get_five_flags_stocks():
    """获取老鸭头股票池列表"""
    # 从 lao_ya_tou_pool 表查询未处理的股票
    # 返回：{success: true, data: [stock_list]}
    pass

@app.route('/api/five-flags/results', methods=['GET'])
def get_five_flags_results():
    """筛选老鸭头五旗结果"""
    # 调用 5 个筛选器
    # 返回：{success: true, data: [result_list]}
    pass

@app.route('/api/five-flags/export', methods=['GET'])
def export_five_flags():
    """导出筛选结果"""
    # 生成 CSV/Excel
    # 返回文件下载
    pass
```

**文件位置：**
- 新建：`backend/routes/five_flags_routes.py`
- 修改：`backend/app.py` 注册路由

### 10.2 前端页面（React + TypeScript）

```typescript
// 文件结构
frontend/src/
  ├── pages/
  │   └── FiveFlagsPage.tsx        # 主页面
  ├── types/
  │   └── five-flags.ts            # 类型定义
  └── api/
      └── five-flags.ts            # API 调用
```

**组件职责：**
- `FiveFlagsPage.tsx`：主页面，管理所有状态和布局
- `StockListPanel`：左侧面板，股票选择和操作按钮
- `FilterSettingsPanel`：右侧筛选设置区
- `ResultsPanel`：右侧结果展示区

### 10.3 Dashboard 集成

```tsx
// frontend/src/pages/MonitorV2.tsx 或 App.tsx
// 添加快捷入口链接
// 不共享状态，仅提供导航
```

---

## 十一、验收标准

### 11.1 功能完整性
- ✅ 页面可独立访问（不通过 Dashboard）
- ✅ 股票列表正常加载和显示
- ✅ 5 个筛选器全部可勾选/取消
- ✅ 筛选结果正确展示（股票代码、名称、筛选器、日期、价格）
- ✅ 导出 CSV/Excel 功能正常
- ✅ 错误提示友好且明确

### 11.2 性能要求
- ✅ 页面首次加载 < 2 秒
- ✅ 筛选响应 < 3 秒（单只股票）
- ✅ 导出功能 < 5 秒

### 11.3 兼容性
- ✅ 支持桌面端（Chrome, Safari, Firefox）
- ✅ 支持移动端响应式布局
- ✅ 不影响 Dashboard 现有功能

### 11.4 可维护性
- ✅ 代码模块化，职责清晰
- ✅ 类型定义完整（TypeScript）
- ✅ 独立路由和 API，易于扩展

---

## 十二、风险控制

### 12.1 已知风险
- ⚠️ **后端数据依赖**：依赖 `lao_ya_tou_pool` 和 `lao_ya_tou_five_flags` 表
- ⚠️ **筛选器性能**：单只股票筛选可能较慢，需要前端加载状态
- ⚠️ **日期范围限制**：不支持跨年查询，限制在 1 年内

### 12.2 缓解方案
- 💡 **前端缓存**：股票列表缓存 5 分钟
- 💡 **分页加载**：结果分页，避免一次性加载过多数据
- 💡 **进度提示**：长时间操作显示进度百分比
- 💡 **错误降级**：API 失败时提供"重试"按钮

---

## 十三、下一步行动

1. ⏳ **UI 设计确认** - 等待用户确认此设计文档
2. ⏸️ **后端 API 开发** - 实现 Flask 路由和业务逻辑
3. ⏸️ **前端页面开发** - 实现 React 组件和交互逻辑
4. ⏸️ **Dashboard 集成** - 添加快捷入口链接
5. ⏸️ **测试验证** - 功能测试和性能测试
6. ⏸️ **文档更新** - 更新 TECHNICAL_DOCS 和用户手册

---

**设计文档版本：** V1.0
**最后更新：** 2026-04-20
**状态：** 📋 等待确认
