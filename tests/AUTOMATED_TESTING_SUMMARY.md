# 筛选器自动化测试系统创建完成

## 📦 已创建的文件

### 1. 测试配置
- `playwright.config.ts` - Playwright 测试配置文件
- `package.json` - 更新了测试脚本

### 2. 测试脚本
- `tests/screener-test.spec.ts` - 筛选器自动化测试套件
  - ✅ 测试筛选器运行和结果显示
  - ✅ 测试配置参数修改和保存
  - ✅ 测试单只股票 CHECK 功能
  - ✅ 完整工作流测试

### 3. 辅助脚本
- `scripts/run_screener_tests.sh` - 快速运行测试的 Shell 脚本

### 4. 文档
- `tests/README.md` - 测试框架完整文档
- `tests/TESTING_GUIDE.md` - 中文快速指南

## 🚀 使用方法

### 基础使用

```bash
# 运行所有测试
npm test

# UI 模式（推荐用于调试）
npm run test:ui

# 调试模式（单步执行）
npm run test:debug

# 查看测试报告
npm run test:report

# 使用快速脚本
bash scripts/run_screener_tests.sh
```

### 配置测试

编辑 `tests/screener-test.spec.ts`:

```typescript
// 修改认证密码（重要！）
const AUTH_PASSWORD = '你的实际密码';

// 修改测试的筛选器
const SCREENER_NAME = 'lao_ya_tou_zhou_xian_screener';
const TEST_STOCK_CODE = '000001';
```

## 📋 测试覆盖的三个关键功能

### 1. 筛选器运行和结果显示
- ✓ 导航到筛选器页面
- ✓ 点击运行按钮
- ✓ 设置日期
- ✓ 等待结果加载
- ✓ 验证结果显示

### 2. 配置参数修改和保存
- ✓ 打开配置弹窗
- ✓ 修改参数
- ✓ 保存配置
- ✓ 验证保存成功
- ✓ 确认值已持久化

### 3. 单只股票 CHECK 功能
- ✓ 导航到单股检查
- ✓ 输入股票代码
- ✓ 运行检查
- ✓ 验证结果显示

## 🔧 为新筛选器添加测试

### 简单步骤

1. **复制测试文件**
```bash
cp tests/screener-test.spec.ts tests/my-screener-test.spec.ts
```

2. **修改配置**
```typescript
const SCREENER_NAME = 'my_screener';
const SCREENER_DISPLAY_NAME = 'My Screener';
```

3. **运行测试**
```bash
npx playwright test tests/my-screener-test.spec.ts
```

### 自定义配置参数

如果筛选器有特定的配置参数，在测试中修改：

```typescript
const testConfig = {
  'param1': 'value1',
  'param2': 'value2',
};
await modifyAndSaveConfig(page, SCREENER_NAME, testConfig);
```

## 🐛 调试技巧

### 1. UI 模式调试
```bash
npm run test:ui
```
- 实时查看浏览器状态
- 单步执行测试
- 检查 DOM 结构

### 2. 使用 Playwright Inspector
```bash
npx playwright codegen http://localhost:8765
```
- 自动生成测试代码
- 找到正确的元素选择器

### 3. 查看失败截图
```bash
ls -la test-results/*/
```

### 4. 查看执行轨迹
```bash
npx playwright show-trace test-results/test-name/trace.zip
```

## ⚠️ 前置条件

### 1. Flask Dashboard 必须运行

```bash
# 检查是否运行
lsof -i :8765

# 启动（如果未运行）
launchctl kickstart -k gui/$(id -u)/com.neotrade2.flask
```

### 2. Playwright 浏览器已安装

```bash
# 安装浏览器（首次运行）
npx playwright install chromium
```

### 3. 认证密码正确

```bash
# 检查实际密码
grep DASHBOARD_PASSWORD /Users/mac/NeoTrade2/config/.env

# 更新测试配置
# 编辑 tests/screener-test.spec.ts
const AUTH_PASSWORD = '实际密码';
```

## 📊 测试输出

### 成功输出
```
✓ All tests passed!

View test report:
  npx playwright show-report
```

### 失败输出
```
❌ Some tests failed

View test report:
  npx playwright show-report

View screenshots and videos in test-results/
```

## 🎯 下一步

### 立即使用

1. **更新测试配置**（修改密码）
```bash
# 编辑 tests/screener-test.spec.ts
# 修改 AUTH_PASSWORD 为你的实际密码
```

2. **运行测试验证老鸭头筛选器**
```bash
npm test
```

3. **查看测试报告**
```bash
npm run test:report
```

### 为其他筛选器添加测试

1. 复制测试文件
2. 修改筛选器名称
3. 自定义配置参数（如果需要）
4. 运行测试验证

## 📚 相关文档

- **完整文档**: `tests/README.md`
- **快速指南**: `tests/TESTING_GUIDE.md`
- **Playwright 官方文档**: https://playwright.dev

## 💡 最佳实践

1. **每次添加/更新筛选器后运行测试**
   ```bash
   npm test
   ```

2. **使用 UI 模式开发新测试**
   ```bash
   npm run test:ui
   ```

3. **在 HTML 中使用 data-testid**
   ```html
   <button data-testid="run-screener">运行</button>
   ```

4. **为每个筛选器创建独立的测试文件**
   ```bash
   tests/lao_ya_tou-test.spec.ts
   tests/coffee_cup-test.spec.ts
   tests/my_screener-test.spec.ts
   ```

---

**创建日期**: 2026-04-16
**状态**: ✅ 完成
**下一步**: 运行测试验证老鸭头筛选器
