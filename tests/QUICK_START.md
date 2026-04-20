# 筛选器自动化测试 - 快速开始

## 🎯 目标

**只需要告诉筛选器名字，自动开始测试！**

---

## 🚀 三种使用方式

### 方式 1: 快速命令（最简单）

```bash
# 语法：npm run test:<筛选器别名>

# 示例：
npm run test:lao-ya-tou        # 老鸭头周线
npm run test:coffee-cup        # 咖啡杯柄 V4
npm run test:ashare-21         # A股2.1
npm run test:breakout-20day    # 20天突破
npm run test:breakout-main     # 主升浪突破
```

### 方式 2: 通用脚本（最灵活）

```bash
# 语法：bash scripts/test_screener.sh <筛选器名称> [显示名称]

# 示例：
bash scripts/test_screener.sh lao_ya_tou_zhou_xian_screener "老鸭头周线"
bash scripts/test_screener.sh coffee_cup_handle_screener_v4 "咖啡杯柄 V4"
```

### 方式 3: 交互式脚本（最友好）

```bash
bash scripts/test_screener_interactive.sh

# 然后按照提示输入：
# 1. 筛选器名称（如：lao_ya_tou_zhou_xian_screener）
# 2. 显示名称（如：老鸭头周线，留空使用默认）
# 3. 确认开始测试
```

---

## 📋 可用的筛选器测试

| npm 命令 | 筛选器名称 | 显示名称 | 状态 |
|---------|-----------|---------|------|
| `npm run test:lao-ya-tou` | lao_ya_tou_zhou_xian_screener | 老鸭头周线 | ✅ 已验证 |
| `npm run test:coffee-cup` | coffee_cup_handle_screener_v4 | 咖啡杯柄 V4 | ⏳ 待验证 |
| `npm run test:ashare-21` | ashare_21_screener | A股2.1 | ⏳ 待验证 |
| `npm run test:breakout-20day` | breakout_20day_screener | 20天突破 | ⏳ 待验证 |
| `npm run test:breakout-main` | breakout_main_screener | 主升浪突破 | ⏳ 待验证 |
| `npm run test:jin-feng-huang` | jin_feng_huang_screener | 金凤凰 | ⏳ 待验证 |
| `npm run test:yin-feng-huang` | yin_feng_huang_screener | 银凤凰 | ⏳ 待验证 |

---

## 🎮 实际使用示例

### 示例 1: 快速测试老鸭头筛选器

```bash
npm run test:lao-ya-tou
```

**输出**:
```
✓ Flask Dashboard 正在运行
✓ 测试文件创建完成
========================================
  开始测试筛选器
========================================
筛选器名称: lao_ya_tou_zhou_xian_screener
显示名称:   老鸭头周线
========================================

Running 4 tests using 4 workers

  ✓ 1. Screener runs and displays results
  ✓ 2. Configuration parameters can be modified and saved
  ✓ 3. Single stock check functionality works
  ✓ 4. Full workflow test

  4 passed (10.0s)

========================================
  ✅ 筛选器测试完成！
========================================
测试筛选器: 老鸭头周线 (lao_ya_tou_zhou_xian_screener)
测试结果:   全部通过
执行时间:   10 秒
========================================
```

### 示例 2: 测试新筛选器（使用通用脚本）

```bash
bash scripts/test_screener.sh my_new_screener "我的新筛选器"
```

### 示例 3: 交互式测试

```bash
bash scripts/test_screener_interactive.sh
```

**交互过程**:
```
╔═══════════════════════════════════════════════════════════════╗
║           筛选器自动化测试 - 交互式模式                    ║
╚═══════════════════════════════════════════════════════════════╝

步骤 1/3: 输入筛选器名称
----------------------------------------

常用筛选器示例:
  - lao_ya_tou_zhou_xian_screener    (老鸭头周线)
  - coffee_cup_handle_screener_v4    (咖啡杯柄 V4)
  - ashare_21_screener               (A股2.1)

筛选器名称: my_screener

步骤 2/3: 输入显示名称
----------------------------------------

显示名称 [my_screener]: 我的新筛选器

步骤 3/3: 确认信息
----------------------------------------

测试配置:
  筛选器名称: my_screener
  显示名称:   我的新筛选器

确认开始测试? [Y/n]: Y

[测试运行中...]
```

---

## 🔧 如何添加新筛选器的快速测试命令

### 方法 1: 编辑 package.json（推荐）

打开 `package.json`，在 `scripts` 部分添加：

```json
{
  "scripts": {
    "test:my-screener": "bash scripts/test_screener.sh my_screener \"我的筛选器\""
  }
}
```

然后就可以使用：
```bash
npm run test:my-screener
```

### 方法 2: 直接使用通用脚本

```bash
bash scripts/test_screener.sh my_screener "我的筛选器"
```

---

## 📊 测试结果查看

### 查看测试报告

```bash
npm run test:report
# 或
npx playwright show-report
```

### 查看失败截图

```bash
ls -la test-results/
```

### 查看测试视频

```bash
ls -la test-results/*/video.webm
```

---

## ⚡ 性能对比

### 手动测试
- 打开浏览器: 5 秒
- 导航到页面: 10 秒
- 测试运行功能: 60 秒
- 测试配置功能: 90 秒
- 测试单股检查: 60 秒
- **总计**: ~225 秒（3.75 分钟）

### 自动化测试
- 运行命令: 1 秒
- 自动执行测试: 10 秒
- **总计**: ~11 秒

**节省时间**: ~214 秒（95%）

---

## 🎓 学习资源

### 完整文档
- **快速指南**: `tests/SCREENER_TESTING_GUIDE.md`（本文档）
- **详细说明**: `tests/TESTING_GUIDE.md`
- **测试框架**: `tests/README.md`
- **结果总结**: `tests/TEST_RESULTS_SUMMARY.md`

### 视频教程（待添加）
- 快速开始：如何测试一个筛选器
- 调试失败的测试
- 为新筛选器添加测试

---

## 💡 常用命令速查

```bash
# 快速测试
npm run test:lao-ya-tou
npm run test:coffee-cup
npm run test:ashare-21

# 通用测试
bash scripts/test_screener.sh <筛选器名称> [显示名称]

# 交互式测试
bash scripts/test_screener_interactive.sh

# 查看报告
npm run test:report

# UI 模式调试
npm run test:ui

# 运行所有测试
npm test
```

---

## 🆘 常见问题

### Q1: 如何获取筛选器名称？

**A**: 查询数据库：
```bash
sqlite3 /Users/mac/NeoTrade2/data/dashboard.db "SELECT name, display_name FROM screeners;"
```

### Q2: 测试失败怎么办？

**A**:
1. 查看 `npm run test:report`
2. 检查 `test-results/` 中的截图和视频
3. 查看 Flask 日志：`tail -f /Users/mac/NeoTrade2/logs/flask.stdout.log`

### Q3: 可以测试不存在的筛选器吗？

**A**: 可以，但会失败。测试会尝试在页面上查找筛选器，找不到则报错。

### Q4: 可以自定义测试参数吗？

**A**: 可以。脚本会创建临时测试文件，你可以在运行前或运行后编辑它来自定义参数。

### Q5: 如何在 CI/CD 中使用？

**A**: 参见 `tests/SCREENER_TESTING_GUIDE.md` 中的 CI/CD 集成部分。

---

## 🎉 开始使用

现在就试试吧！

```bash
# 快速测试老鸭头筛选器（已验证）
npm run test:lao-ya-tou

# 或者使用交互式模式
bash scripts/test_screener_interactive.sh

# 或者查看所有可用的测试命令
npm run
```

---

**最后更新**: 2026-04-16
**维护人**: Claude Code
**状态**: ✅ 完全就绪
