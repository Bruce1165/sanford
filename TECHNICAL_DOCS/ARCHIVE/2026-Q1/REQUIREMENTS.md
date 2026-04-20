# 📋 Neo Trading Analytics - 项目需求文档 (PRD)

**文档版本**: 1.0  
**创建日期**: 2026-03-19  
**项目经理**: Neo  
**状态**: 需求梳理中

---

## 🎯 项目愿景

构建一个完整的A股股票技术分析系统，支持自动化数据获取、多维度筛选、可视化展示和实时监控。

---

## 📊 已确认功能模块

### 1. 数据基础设施 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| 数据采集 | ✅ | Baostock → SQLite |
| 数据更新 | ✅ | 每日自动更新4663只股票 |
| 数据质量 | ✅ | 唯一约束、幂等性、重复检测 |
| 数据监控 | ✅ | SRE健康检查脚本 |
| 断点续传 | ✅ | 支持中断恢复 |

**数据表**:
- `stocks` - 股票基础信息
- `daily_prices` - 日行情数据
- `announcements` - 公告数据
- `limit_up_reasons` - 涨停原因

---

### 2. 筛选器系统 🏗️

| 筛选器 | 中文名 | 类型 | 状态 |
|--------|--------|------|------|
| coffee_cup_screener | 咖啡杯形态 | 欧奈尔形态 | 🏗️ 修复中 |
| jin_feng_huang_screener | 涨停金凤凰 | 涨停回调 | 🏗️ 修复中 |
| yin_feng_huang_screener | 涨停银凤凰 | 涨停回调 | 🏗️ 修复中 |
| shi_pan_xian_screener | 涨停试盘线 | 涨停形态 | 🏗️ 修复中 |
| er_ban_hui_tiao_screener | 二板回调 | 连板回调 | 🏗️ 修复中 |
| zhang_ting_bei_liang_yin_screener | 涨停倍量阴 | 量价形态 | 🏗️ 修复中 |
| breakout_20day_screener | 20日突破 | 突破形态 | 🏗️ 修复中 |
| breakout_main_screener | 主升突破 | 趋势突破 | 🏗️ 修复中 |
| daily_hot_cold_screener | 每日热冷股 | 市场情绪 | 🏗️ 修复中 |
| shuang_shou_ban_screener | 双收板 | 涨停形态 | 🏗️ 修复中 |
| ashare_21_screener | A股21选股 | 综合选股 | 🏗️ 修复中 |

**筛选器功能**:
- 本地SQLite数据分析
- 技术指标计算
- 形态识别
- 结果导出Excel

---

### 3. Dashboard可视化 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| 筛选器列表 | ✅ | 11个筛选器展示 |
| 结果表格 | ✅ | 中文列名、排序 |
| K线图表 | ✅ | ECharts集成 |
| 日期选择 | ✅ | 日历组件 |
| Excel导出 | ✅ | 一键下载 |
| 密码保护 | ✅ | Basic Auth |

**访问方式**:
- URL: ngrok隧道
- 认证: admin/bruce2024

---

### 4. 自动化任务 ✅

| 任务 | 频率 | 状态 |
|------|------|------|
| 数据下载 | 每日 | ✅ |
| 数据健康检查 | 每小时 | ✅ |
| Ngrok监控 | 持续 | ✅ |
| 筛选器QA | 每日 | ✅ |

---

### 5. 团队/代理系统 ✅

| 角色 | 代理 | 职责 |
|------|------|------|
| PM | Neo | 统筹协调 |
| Data Engineer | engineering-data-engineer | 数据管道 |
| DB Optimizer | engineering-database-optimizer | 数据库优化 |
| DevOps | engineering-devops-automator | CI/CD、自动化 |
| Backend Architect | engineering-backend-architect | API、筛选器 |
| SRE | engineering-sre | 可靠性、监控 |
| Tech Writer | engineering-technical-writer | 文档 |
| Frontend Dev | engineering-frontend-developer | Dashboard |
| Daily QA | testing-test-results-analyzer | 每日QA |

---

## ❓ 待确认需求 (已确认 ✅)

### 🔴 高优先级问题

1. **筛选器运行频率** ✅
   - **确认**: 数据成功下载后自动运行
   - **状态**: 已配置 - 见 `scripts/daily_update_screener.py` 钩子

2. **实时沟通机制** ✅
   - **确认**: 出现问题立即通知Bruce
   - **方式**: 通过当前OpenClaw对话通道
   - **内容**: 问题描述 + 原因 + 解决结果

3. **新闻抓取** ✅
   - **确认**: 暂时关闭
   - **状态**: 已禁用 (enable_news=False)

### 🟡 中优先级问题

4. **告警通知方式**
   - 问题: 发现问题时如何通知？
   - 选项:
     - A. 邮件 (需要配置SMTP)
     - B. 钉钉/飞书 (需要Webhook)
     - C. 仅日志记录
     - D. Dashboard显示
   - 当前: 仅日志 + Dashboard

5. **数据保留策略**
   - 问题: 历史数据保留多久？
   - 当前: 永久保留
   - 建议: 保留2-3年

6. **筛选结果存档**
   - 问题: 历史筛选结果是否保留？
   - 当前: 每次运行覆盖
   - 建议: 按日期归档

### 🟢 低优先级问题

7. **移动端支持**
   - 问题: 是否需要移动端Dashboard？
   - 当前: Web响应式
   - 建议: 后续考虑

8. **多用户支持**
   - 问题: 是否需要多用户权限？
   - 当前: 单用户
   - 建议: 暂不需要

9. **回测功能**
   - 问题: 是否需要策略回测？
   - 建议: 后续版本考虑

---

## 📅 开发路线图

### Phase 1: 基础设施 (已完成 ✅)
- [x] 数据采集系统
- [x] 数据质量保证
- [x] Dashboard基础
- [x] 监控告警

### Phase 2: 筛选器完善 (进行中 🏗️)
- [ ] 修复所有筛选器bug
- [ ] 每日自动运行
- [ ] 结果归档

### Phase 3: 功能增强 (待规划 📋)
- [ ] 新闻抓取 (可选)
- [ ] LLM分析 (可选)
- [ ] 回测功能
- [ ] 移动端优化

---

## 📝 待沟通事项

请Bruce确认以下问题：

### 立即确认 (影响当前开发)
1. **筛选器运行频率** - 每日自动还是手动？
2. **告警方式** - 需要邮件/钉钉通知吗？
3. **新闻抓取** - 是否需要？（会影响稳定性）

### 后续确认 (影响长期规划)
4. **数据保留期** - 保留多久的历史数据？
5. **筛选结果存档** - 需要保留历史筛选结果吗？
6. **回测功能** - 需要策略回测吗？

---

**最后更新**: 2026-03-19 10:22 by Neo
