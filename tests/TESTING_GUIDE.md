# 筛选器自动化测试快速指南

## 🚀 快速开始

### 1. 验证环境

```bash
# 检查 Flask 是否运行
curl http://localhost:8765

# 检查 Playwright 是否安装
npx playwright --version
```

### 2. 运行测试

```bash
# 方式 1: 使用 npm 脚本（推荐）
npm test                  # 运行所有测试
npm run test:ui           # UI 模式运行（带浏览器预览）
npm run test:debug        # 调试模式（单步执行）

# 方式 2: 使用快速脚本
bash scripts/run_screener_tests.sh              # 运行所有测试
bash scripts/run_screener_tests.sh --ui         # UI 模式
bash scripts/run_screener_tests.sh --debug      # 调试模式
bash scripts/run_screener_tests.sh --help       # 查看帮助
```

### 3. 查看测试报告

```bash
npm run test:report
# 或
npx playwright show-report
```

## 📋 测试覆盖的三个关键功能

### 1️⃣ 筛选器运行和结果显示

测试步骤：
- ✓ 导航到筛选器页面
- ✓ 点击"运行"按钮
- ✓ 设置日期
- ✓ 等待结果加载
- ✓ 验证结果显示或"无结果"消息

**验证点：**
- 运行按钮可点击
- 结果表格正确显示
- 每行结果包含股票代码、名称等信息

### 2️⃣ 配置参数修改和保存

测试步骤：
- ✓ 点击"配置"按钮
- ✓ 打开配置弹窗
- ✓ 修改测试参数（如 min_weeks = 65）
- ✓ 点击"保存"按钮
- ✓ 等待保存成功提示
- ✓ 重新打开配置验证值已保存

**验证点：**
- 配置弹窗正常打开
- 参数可以修改
- 保存成功提示显示
- 配置值持久化保存

### 3️⃣ 单只股票 CHECK 功能

测试步骤：
- ✓ 导航到筛选器页面
- ✓ 点击"单股检查"标签
- ✓ 输入测试股票代码（000001）
- ✓ 点击"检查"按钮
- ✓ 等待检查结果
- ✓ 验证结果或错误信息

**验证点：**
- 单股检查界面正常显示
- 可以输入股票代码
- 检查功能执行
- 结果正确显示

## 🔧 测试配置

### 修改测试参数

编辑 `tests/screener-test.spec.ts`:

```typescript
// 修改认证密码
const AUTH_PASSWORD = '你的实际密码';

// 修改测试的筛选器
const SCREENER_NAME = '你的筛选器名称';
const SCREENER_DISPLAY_NAME = '筛选器显示名称';

// 修改测试股票代码
const TEST_STOCK_CODE = '000001';
```

### 添加新筛选器测试

1. 复制现有测试文件：
```bash
cp tests/screener-test.spec.ts tests/my-screener-test.spec.ts
```

2. 修改配置：
```typescript
const SCREENER_NAME = 'my_screener';
const SCREENER_DISPLAY_NAME = 'My Screener';
```

3. 如果需要，自定义配置参数：
```typescript
const testConfig = {
  'custom_param1': 'value1',
  'custom_param2': 'value2',
};
```

## 🐛 调试失败的测试

### 查看失败截图

```bash
# 失败测试自动保存截图到
ls -la test-results/*/
```

### 查看执行轨迹

```bash
npx playwright show-trace test-results/test-name/trace.zip
```

### 使用 UI 模式调试

```bash
npm run test:ui
```

- 可以看到每个步骤的浏览器状态
- 可以点击"step"按钮单步执行
- 可以检查元素和 DOM 结构

### 使用 Playwright Inspector 生成选择器

```bash
npx playwright codegen http://localhost:8765
```

- 在浏览器中操作页面
- Playwright 自动生成代码
- 复制需要的选择器

## ⚠️ 常见问题

### 问题 1: "Page not found" 或 404

**原因**: Flask 没有运行或端口不对

**解决**:
```bash
# 检查 Flask 是否运行
lsof -i :8765

# 如果没有运行，启动它
launchctl kickstart -k gui/$(id -u)/com.neotrade2.flask
```

### 问题 2: 认证失败

**原因**: 测试中的密码与实际密码不匹配

**解决**:
```bash
# 检查实际密码
grep DASHBOARD_PASSWORD /Users/mac/NeoTrade2/config/.env

# 更新测试文件中的密码
# 编辑 tests/screener-test.spec.ts
const AUTH_PASSWORD = '你的实际密码';
```

### 问题 3: "Element not found" 错误

**原因**: HTML 结构变化，选择器不匹配

**解决**:
1. 使用 Playwright Inspector 查找正确的选择器
2. 更新测试文件中的选择器
3. 或者在 HTML 中添加 `data-testid` 属性

```html
<!-- 推荐：使用 data-testid -->
<button data-testid="run-screener">运行</button>

<!-- 不推荐：使用 class -->
<button class="btn-primary">运行</button>
```

### 问题 4: 测试超时

**原因**: API 响应慢或数据量大

**解决**:
```typescript
// 增加超时时间
test('slow test', { timeout: 120000 }, async ({ page }) => {
  // 测试代码
});
```

### 问题 5: Playwright 浏览器未安装

**原因**: 第一次运行时浏览器没有安装

**解决**:
```bash
npx playwright install chromium
```

## 📊 持续集成

在 GitHub Actions 中运行测试：

```yaml
name: Run Tests

on: [push, pull_request]

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

      - name: Install Playwright browsers
        run: npx playwright install --with-deps chromium

      - name: Run tests
        run: npm test

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/
```

## 🎯 测试最佳实践

1. **使用描述性测试名称**
   - ✅ "Screener runs and displays results"
   - ❌ "Test 1"

2. **使用 data-testid 选择器**
   - ✅ `page.getByTestId('run-button')`
   - ❌ `page.locator('.btn-primary')`

3. **等待网络空闲**
   ```typescript
   await page.waitForLoadState('networkidle');
   ```

4. **使用 Playwright fixtures**
   - 自动页面清理
   - 独立测试环境

5. **添加有意义的断言**
   ```typescript
   await expect(successMessage).toContainText('保存成功');
   ```

## 📚 相关资源

- [Playwright 官方文档](https://playwright.dev)
- [Playwright 最佳实践](https://playwright.dev/docs/best-practices)
- [测试生成器](https://playwright.dev/docs/codegen)
- [轨迹查看器](https://playwright.dev/docs/trace-viewer)

---

**快速命令参考**:
```bash
npm test              # 运行所有测试
npm run test:ui       # UI 模式
npm run test:debug    # 调试模式
npm run test:report   # 查看报告
```

**最后更新**: 2026-04-16
