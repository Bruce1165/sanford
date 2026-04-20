# 筛选器自动化测试快速指南

## 🎯 目标

**只需要告诉筛选器名字，自动开始测试！**

## 🚀 使用方法

### 方式 1: 命令行快速测试（推荐）

```bash
# 语法：bash scripts/test_screener.sh <筛选器名称> [显示名称]

# 示例 1: 测试老鸭头筛选器
bash scripts/test_screener.sh lao_ya_tou_zhou_xian_screener "老鸭头周线"

# 示例 2: 测试咖啡杯柄筛选器
bash scripts/test_screener.sh coffee_cup_handle_screener_v4 "咖啡杯柄 V4"

# 示例 3: 只传筛选器名称（自动使用默认显示名称）
bash scripts/test_screener.sh coffee_cup_handle_screener_v4
```

### 方式 2: 交互式测试

```bash
# 运行交互式脚本
bash scripts/test_screener_interactive.sh

# 按照提示输入筛选器名称和显示名称
```

### 方式 3: 使用 npm 脚本

```bash
# 快速测试常用筛选器
npm run test:lao-ya-tou      # 老鸭头
npm run test:coffee-cup      # 咖啡杯柄
npm run test:ashare-21       # A股2.1

# 或者使用通用命令
npm run test:screener -- lao_ya_tou_zhou_xian_screener "老鸭头周线"
```

---

## 📋 测试覆盖的三个关键功能

### 1. ✓ 筛选器运行和结果显示
- 导航到筛选器页面
- 验证筛选器存在于列表中
- 验证筛选器信息正确显示

### 2. ✓ 配置参数修改和保存
- 打开配置弹窗
- 修改参数
- 保存配置
- 验证保存成功

### 3. ✓ 单只股票 CHECK 功能
- 输入股票代码
- 选择筛选器
- 运行检查
- 验证结果显示

---

## 📖 详细说明

### 筛选器名称和显示名称

**筛选器名称** (screener_name):
- 数据库中的唯一标识符
- 例如: `lao_ya_tou_zhou_xian_screener`, `coffee_cup_handle_screener_v4`
- 用于 API 调用和内部引用

**显示名称** (display_name):
- 用户界面上显示的名称
- 例如: `老鸭头周线`, `咖啡杯柄 V4`
- 用于测试时识别筛选器

### 如何获取筛选器名称？

**方法 1: 从数据库查询**
```bash
sqlite3 /Users/mac/NeoTrade2/data/dashboard.db "SELECT name, display_name FROM screeners;"
```

**方法 2: 从浏览器开发者工具**
1. 打开 Dashboard
2. 打开开发者工具 (F12)
3. 切换到 Network 标签
4. 点击任意筛选器的配置按钮
5. 查看 API 请求中的参数

**方法 3: 从代码中查找**
```bash
grep -r "register_screener" screeners/ backend/
```

---

## 🛠️ 工作原理

### 快速测试脚本流程

1. **参数验证**
   - 检查筛选器名称是否提供
   - 如果没有提供显示名称，自动生成

2. **创建临时测试文件**
   - 基于模板生成测试文件
   - 填入筛选器名称和显示名称

3. **运行测试**
   - 执行 Playwright 测试
   - 收集测试结果

4. **生成报告**
   - 创建测试报告
   - 显示结果摘要

5. **清理**
   - 删除临时测试文件（可选）

### 交互式脚本流程

1. **询问筛选器名称**
   - 提示用户输入筛选器名称
   - 验证输入

2. **询问显示名称（可选）**
   - 如果未提供，自动生成

3. **确认信息**
   - 显示将要测试的筛选器信息
   - 等待用户确认

4. **运行测试**
   - 同快速测试脚本

5. **显示结果**
   - 显示详细的测试结果
   - 提供后续操作建议

---

## 📊 测试结果解读

### 成功输出

```
✅ 筛选器测试完成！

测试筛选器: 老鸭头周线 (lao_ya_tou_zhou_xian_screener)

测试结果:
  ✓ 1. 筛选器运行和结果显示
  ✓ 2. 配置参数修改和保存
  ✓ 3. 单只股票 CHECK 功能
  ✓ 4. 完整工作流

通过: 4/4 (100%)
执行时间: 10.2 秒

查看详细报告:
  npx playwright show-report
```

### 失败输出

```
❌ 测试失败！

测试筛选器: 老鸭头周线 (lao_ya_tou_zhou_xian_screener)

失败的测试:
  ✗ 2. 配置参数修改和保存
  ✗ 3. 单只股票 CHECK 功能

通过: 2/4 (50%)
执行时间: 15.3 秒

查看失败详情:
  npx playwright show-report

查看截图和视频:
  ls -la test-results/
```

---

## 🎨 高级用法

### 自定义测试参数

编辑临时测试文件修改参数：

```typescript
// 修改测试股票代码
const TEST_STOCK_CODE = '600000';  // 改为浦发银行

// 修改超时时间
test('test name', { timeout: 60000 }, async ({ page }) => {
  // 测试代码
});
```

### 只运行特定测试

```bash
# 只测试运行功能
npx playwright test -g "runs and displays"

# 只测试配置功能
npx playwright test -g "Configuration"

# 只测试单股检查
npx playwright test -g "Single stock"
```

### 并行运行多个筛选器测试

```bash
# 同时测试多个筛选器
npm run test:lao-ya-tou &
npm run test:coffee-cup &
wait
```

### CI/CD 集成

```yaml
# .github/workflows/test-screener.yml
name: Test Screener

on:
  workflow_dispatch:
    inputs:
      screener_name:
        description: 'Screener name to test'
        required: true
      display_name:
        description: 'Screener display name'
        required: false

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright
        run: npx playwright install --with-deps chromium

      - name: Run screener test
        env:
          SCREENER_NAME: ${{ github.event.inputs.screener_name }}
          DISPLAY_NAME: ${{ github.event.inputs.display_name || '' }}
        run: |
          bash scripts/test_screener.sh "$SCREENER_NAME" "$DISPLAY_NAME"

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/
```

---

## 🔧 故障排除

### 问题 1: "筛选器未找到"

**原因**: 筛选器名称不正确或筛选器不存在

**解决**:
```bash
# 查询所有筛选器
sqlite3 /Users/mac/NeoTrade2/data/dashboard.db "SELECT name, display_name FROM screeners;"

# 使用正确的名称重新测试
bash scripts/test_screener.sh <正确名称>
```

### 问题 2: "Flask 未运行"

**原因**: Flask Dashboard 未启动

**解决**:
```bash
# 检查 Flask 状态
lsof -i :8765

# 启动 Flask
launchctl kickstart -k gui/$(id -u)/com.neotrade2.flask
```

### 问题 3: "认证失败"

**原因**: 密码不正确

**解决**:
```bash
# 查看实际密码
grep DASHBOARD_PASSWORD /Users/mac/NeoTrade2/config/.env

# 更新测试配置
# 编辑 tests/screener-test-template.ts
const AUTH_PASSWORD = '实际密码';
```

### 问题 4: "测试超时"

**原因**: 网络慢或数据量大

**解决**:
```bash
# 增加超时时间
npx playwright test --timeout=60000
```

---

## 📚 相关文档

- **完整测试文档**: `tests/README.md`
- **快速指南**: `tests/TESTING_GUIDE.md`
- **测试结果**: `tests/TEST_RESULTS_SUMMARY.md`
- **系统总结**: `tests/AUTOMATED_TESTING_SUMMARY.md`

---

## 💡 最佳实践

1. **每次添加/更新筛选器后运行测试**
   ```bash
   bash scripts/test_screener.sh <筛选器名称>
   ```

2. **使用交互式脚本进行不确定的测试**
   ```bash
   bash scripts/test_screener_interactive.sh
   ```

3. **为常用筛选器创建 npm 脚本**
   ```bash
   # 在 package.json 中添加
   "scripts": {
     "test:lao-ya-tou": "bash scripts/test_screener.sh lao_ya_tou_zhou_xian_screener \"老鸭头周线\"",
     "test:coffee-cup": "bash scripts/test_screener.sh coffee_cup_handle_screener_v4 \"咖啡杯柄 V4\""
   }
   ```

4. **定期运行所有筛选器测试**
   ```bash
   # 创建批量测试脚本
   for screener in lao_ya_tou coffee_cup ashare_21; do
     bash scripts/test_screener.sh $screener
   done
   ```

---

## 🎯 快速参考

### 常用筛选器名称

| 筛选器名称 | 显示名称 | npm 脚本 |
|-----------|---------|---------|
| `lao_ya_tou_zhou_xian_screener` | 老鸭头周线 | `npm run test:lao-ya-tou` |
| `coffee_cup_handle_screener_v4` | 咖啡杯柄 V4 | `npm run test:coffee-cup` |
| `ashare_21_screener` | A股2.1 | `npm run test:ashare-21` |
| `breakout_20day_screener` | 20天突破 | - |
| `breakout_main_screener` | 主升浪突破 | - |
| `jin_feng_huang_screener` | 金凤凰 | - |
| `yin_feng_huang_screener` | 银凤凰 | - |

### 快速命令

```bash
# 测试老鸭头（最常用）
bash scripts/test_screener.sh lao_ya_tou_zhou_xian_screener "老鸭头周线"

# 交互式测试
bash scripts/test_screener_interactive.sh

# 查看测试报告
npm run test:report

# UI 模式调试
npm run test:ui
```

---

**最后更新**: 2026-04-16
**维护人**: Claude Code
**状态**: ✅ 完全就绪
