# 文档清单

**最后更新**: 2026-04-10 17:58

---

## 📋 活跃文档（TECHNICAL_DOCS/）

| 文档 | 最后更新 | 状态 | 职责 |
|------|---------|------|
| 00_START_HERE.md | 2026-04-10 | ✅ | 快速入门 |
| 01_START_SERVER.md | 2026-04-10 | ✅ | 启动说明 |
| 02_SYSTEM_CONFIG.md | 2026-04-10 | ✅ | 系统配置（认证、数据库） |
| 03_FLASK_ARCHITECTURE.md | 2026-04-10 | ✅ | 架构设计 |
| 13_FLASK_CPOLAR_SERVICES.md | 2026-04-10 | ✅ | 服务管理 |
| 14_AUTHENTICATION_FIX.md | 2026-04-10 | ✅ | 故障记录 |

**说明**：这些文档遵循严格单一事实来源原则，避免重复。

---

## 📦 已归档文档（docs/archive/）

| 文档 | 说明 |
|------|------|
| excel_upload_field_mapping.html | Excel 字段映射报告 |
| excel_upload_field_mapping.pdf | Excel 字段映射 PDF |
| style.css | 临时 CSS 文件 |
| 欧奈尔杯柄形态选股系统技术白皮书.html | 完成的技术白皮书 |

**说明**：已从 docs/ 移动到 archive/，保留历史参考。

---

## 📸 快照记录（VERSIONS/snapshots/）

| 快照 | 时间 | 说明 |
|------|------|------|
| snapshot-2026-04-10.md | 2026-04-10 17:55 | 技术文档去重完成后状态 |

---

## 🔄 文档管理原则

### 核心原则
1. **单一职责**：每个文档有明确的单一职责
2. **避免重复**：使用引用而非复制内容
3. **明确生命周期**：活跃 → 归档 → 删除
4. **版本追踪**：重要变更记录在 VERSIONS
5. **快照独立**：Dashboard 界面状态与代码版本分离

### 命名规范
| 类型 | 格式 | 示例 |
|------|------|------|
| 快照 | `snapshot-YYYY-MM-DD_HH:MM.md` | snapshot-2026-04-10_17:55.md |
| 技术文档 | `XX_主题.md` | 02_SYSTEM_CONFIG.md |
| 归档 | `archive-年月.md` | archive-2026-04.md |

### 文档分类
| 目录 | 类型 | 生命周期 |
|------|------|--------|
| TECHNICAL_DOCS/ | 技术文档 | 长期维护 |
| VERSIONS/snapshots/ | 快照 | 版本管理 |
| docs/archive/ | 归档 | 历史参考 |
| research/temporary/ | 临时研究 | 定期清理 |
| docs/需求管理/ | 项目需求 | 进行中 → 归档 |

---

**最后检查时间**: 2026-04-10 17:58
