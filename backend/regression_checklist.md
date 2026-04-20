# Regression Checklist

## 🚀 Development Best Practices (CRITICAL)

**BEFORE ANY TESTING OR VALIDATION, Claude Code MUST:**

**Read**: `/Users/mac/NeoTrade2/DEVELOPMENT_BEST_PRACTICES.md`
- Complete development planning and pseudocode before coding
- Follow backup, testing, and quality standards
- Use debugging messages and maintain professional approach

**Key Guidelines**:
1. ✅ **Planning first** - Make development plan, write pseudocode
2. ✅ **Backup before modifying** - Keep backup until verified
3. ✅ **English-only code** - No Chinese characters in real files
4. ✅ **Debug with messages** - Use print statements for tracing
5. ✅ **Stop when stuck** - Ask for help after 15 minutes circular
6. ✅ **Real data only** - No placeholders or fictional examples
7. ✅ **Clean logs** - Remove temporary debug logs after verification

**For testing workflows, see**: `/Users/mac/NeoTrade2/DEVELOPMENT_BEST_PRACTICES.md`

---

## 认证相关（本次修改）
- **[ ] Make development plan before coding**
- **[ ] Design data structures and algorithms first**
- **[ ] Plan testing approach and validation criteria**
- **[ ] Consider edge cases and error handling**
- **[ ] Review existing similar code for patterns**

### 📝 2. Pseudocode Before Real Coding
- **[ ] Write pseudocode file before implementation**
- **[ ] Document algorithm logic and data flow**
- **[ ] Define input/output specifications**
- **[ ] Plan error handling and edge cases

### 💻 3. Update Pseudocode Before Real Code
- **[ ] Update pseudocode file before modifying real code**
- **[ ] Ensure implementation matches pseudocode design**
- **[ ] Document any deviations from pseudocode**
- **[ ] Keep pseudocode as living documentation**

### 🗂️ 4. File Backup and Safety
- **[ ] Backup current file before modifying**
- **[ ] Keep backup until all modifications verified**
- **[ ] Delete backup only after complete verification**
- **[ ] Test backup restore if needed during development

### 🔡 5. Code Quality Standards
- **[ ] NO Chinese characters in real code files**
- **[ ] English variable names and comments only**
- **[ ] Follow existing code style and patterns**
- **[ ] Use descriptive variable and function names**
- **[ ] Add docstrings to new functions and classes**

### 🐛 6. Debugging and Problem Solving
- **[ ] Use debugging messages for tracing execution**
- **[ ] Add debug logging for cache/version issues**
- **[ ] Document critical points and decision logic**
- **[ ] Use print statements for key algorithm steps**
- **[ ] STOP if stuck in circular problem solving - ask for help**

### 🧹 7. Log File Management
- **[ ] Clean up log files after each work chunk**
- **[ ] Remove temporary/debug logs after verification**
- **[ ] Archive old log files periodically**
- **[ ] Keep logs structured and searchable**

### 🎯 8. Real and Professional Approach
- **[ ] Keep it real - no fictional examples or placeholders**
- **[ ] Use actual data and realistic scenarios**
- **[ ] Base decisions on facts and requirements**
- **[ ] Document assumptions and constraints clearly**

### ✅ Pre-Testing Checklist Summary
Before any testing or validation work, Claude Code must:
1. **[ ]** Read development best practices section
2. **[ ] Create comprehensive test plan
3. **[ ] Write pseudocode for test logic
4. **[ ] Plan validation approach and success criteria
5. **[ ] Consider edge cases and error scenarios

---

## 认证相关（本次修改）

- [ ] 本地访问不再弹出登录窗口
- [ ] 外部访问仍然需要密码保护
- [ ] `/api/health` 健康检查端点无需认证
- [ ] 本地IP正确识别（127.0.0.1, localhost, 192.168.x.x, 10.x.x.x, 172.16-31.x.x）

## 现有功能验证

### 筛选器功能
- [ ] 筛选器列表可以正常加载 (`GET /api/screeners`)
- [ ] 筛选器详情可以正常查看 (`GET /api/screeners/<name>`)
- [ ] 筛选器可以正常运行 (`POST /api/screeners/<name>/run`)
- [ ] 筛选器结果可以正常查询 (`GET /api/results`)
- [ ] 筛选器历史运行记录可以正常查询 (`GET /api/runs`)

### 前端功能
- [ ] Dashboard 主页可以正常加载
- [ ] 筛选器监控页面可以正常显示
- [ ] 筛选器结果表格可以正常展示
- [ ] 股票图表可以正常渲染
- [ ] 日期选择器可以正常工作

### 新增配置管理功能
- [ ] 配置API可以正常调用 (`GET /api/screeners/<name>/config`)
- [ ] 配置可以正常更新 (`PUT /api/screeners/<name>/config`)
- [ ] 版本历史可以正常查询 (`GET /api/screeners/<name>/history`)
- [ ] 配置回滚可以正常执行 (`POST /api/screeners/<name>/rollback`)
- [ ] 参数验证正常工作（范围、类型）

### 数据库
- [ ] `screener_configs` 表可以正常读写
- [ ] `screener_config_history` 表可以正常写入
- [ ] 版本自动递增正常（v1.0 → v1.1 → v1.2）

### 配置文件
- [ ] JSON配置文件可以正常读取
- [ ] JSON配置文件可以正常保存
- [ ] 14个筛选器配置文件格式正确

## 性能检查
- [ ] 页面加载时间无明显增加
- [ ] API响应时间无明显增加
- [ ] 没有新的内存泄漏

## 安全检查
- [ ] 外部访问仍然需要密码
- [ ] CORS配置正确
- [ ] 没有暴露敏感信息

---

## 快速验证命令

```bash
# 1. 检查健康端点（无需认证）
curl http://localhost:5003/api/health

# 2. 检查筛选器列表（本地访问无需认证）
curl http://localhost:5003/api/screeners

# 3. 检查配置API（新增功能）
curl http://localhost:5003/api/screeners/er_ban_hui_tiao/config

# 4. 检查前端是否可以访问
curl http://localhost:3000/

# 5. 检查数据库完整性
sqlite3 data/dashboard.db "SELECT COUNT(*) FROM screener_configs;"
sqlite3 data/dashboard.db "PRAGMA integrity_check;"

# 6. 检查配置文件
ls -la config/screeners/
python3 -c "import json; print(json.load(open('config/screeners/er_ban_hui_tiao.json'))['display_name'])"
```

## 已知限制

1. **本地访问认证跳过**: 仅适用于开发环境。生产环境如果部署在同一台机器，需要考虑是否需要强制认证。
2. **环境变量**: `DASHBOARD_PASSWORD` 仍然是必需的（虽然本地访问不需要，但代码中仍然要求设置）。

## 下一步改进建议

1. 添加单元测试覆盖认证逻辑
2. 添加集成测试覆盖新增的配置管理API
3. 添加E2E测试覆盖前端配置编辑器
4. 添加性能监控和日志
5. 考虑使用更灵活的认证方案（如JWT token）
