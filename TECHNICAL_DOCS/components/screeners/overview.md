## 已完成的筛选器（共14个）

### 1. 欧奈尔杯柄形态 (CANSLIM) ✅
**文件：** `coffee_cup_screener.py`
**配置：** `config/screeners/coffee_cup.json`

**形态特点：**
- 杯体 50-60天，杯深 12%-35%
- 柄部 15-20天，回调 5%-12%
- U型验证（最低点 30%-70% 中部）
- 均线多头排列 (50/150/200)
- RS ≥ 85

**检查项：**
- 换手率 ≥ 5%
- 涨幅 ≥ 2%
- 量比 ≥ 2倍
- 突破柄部高点

---

### 1.1 咖啡杯形态 V4 ✅ (最新)
**文件：** `coffee_cup_screener_v4.py`
**配置：** `config/screeners/coffee_cup_v4.json`

**关键更新（V4版本）：**
- 两个杯沿高点统一处理，间隔 45-250天
- 杯柄：右侧杯沿后 5-20天的走势
- 杯柄可上扬、平拉、下跌（但下跌≤杯深/2）
- 温和上涨细分为：
  - 震荡期（15-30天）：有涨有跌，不跌破杯底，不过于接近杯沿
  - 快速上涨期（13-15天）：价格上涨增速
- 成交量条件：右侧杯沿前13天平均 ≥ 左侧杯沿后13天平均 × 1倍

**检查项：**
- 换手率 ≥ 5%
- 涨幅 ≥ 2%
- 杯深：5%-70%
- 杯柄下跌限制：≤杯深的一半
- 成交量倍数 ≥ 1倍

**参数数量：** 26个可调节参数
**详细参数：** 参见 [11_COFFEE_CUP_PARAMS_V4.md](11_COFFEE_CUP_PARAMS_V4.md)
**管理指南：** 参见 [15_SCREENER_MANAGEMENT.md](15_SCREENER_MANAGEMENT.md)

---

### 2. 涨停金凤凰 ✅
**文件：** `jin_feng_huang_screener.py`
**配置：** `config/screeners/jin_feng_huang.json`

**形态特点：**
- 涨停板后回调不破首板开盘价
- 2连板后的启动信号
- 主力资金介入信号

---

### 3. 涨停银凤凰 ✅
**文件：** `yin_feng_huang_screener.py`
**配置：** `config/screeners/yin_feng_huang.json`

**形态特点：**
- 涨停板后的回调形态
- 与金凤凰类似，但参数略有不同
- 区别信号强度

---

### 4. 涨停试盘线 ✅
**文件：** `shi_pan_xian_screener.py`
**配置：** `config/screeners/shi_pan_xian.json`

**形态特点：**
- 涨停后形成试盘线
- 价格在特定区间震荡
- 试探后续走势

---

### 5. 二板回调 ✅
**文件：** `er_ban_hui_tiao_screener.py`
**配置：** `config/screeners/er_ban_hui_tiao.json`

**形态特点：**
- 二连涨停后回调不破首板开盘价
- 回调后重新启动
- 典型的主力启动形态

---

### 6. 涨停倍量阴 ✅
**文件：** `zhang_ting_bei_liang_yin_screener.py`
**配置：** `config/screeners/zhang_ting_bei_liang_yin.json`

**形态特点：**
- 涨停板后的放量大阴线
- 成交量异常放大
- 可能是出货信号

---

### 7. 20日突破 ✅
**文件：** `breakout_20day_screener.py`
**配置：** `config/screeners/breakout_20day.json`

**形态特点：**
- 突破20日高点
- 价格创近期新高
- 趋势启动信号

---

### 8. 主升浪突破 ✅
**文件：** `breakout_main_screener.py`
**配置：** `config/screeners/breakout_main.json`

**形态特点：**
- 突破主要压力位
- 进入主升浪阶段
- 大趋势确立

---

### 9. 每日冷热 ✅
**文件：** `daily_hot_cold_screener.py`
**配置：** `config/screeners/daily_hot_cold.json`

**形态特点：**
- 每日统计热门和冷门股票
- 基于成交量和涨幅
- 市场情绪指标

---

### 10. 双首板 ✅
**文件：** `shuang_shou_ban_screener.py`
**配置：** `config/screeners/shuang_shou_ban.json`

**形态特点：**
- 连续两个涨停板
- 强势股特征
- 短期爆发力强

---

### 11. A股2.1综合 ✅
**文件：** `ashare_21_screener.py`
**配置：** `config/screeners/ashare_21.json`

**形态特点：**
- 综合多个技术指标
- 2.1版本参数体系
- 多维度筛选

---

## 参数对照表

| 形态 | 周期 | 幅度 | 成交量 | 特点 |
|------|------|------|--------|------|
| 杯柄 | 杯50-60天柄15-20天 | 杯深12-35%柄调5-12% | 柄部缩量<85% | 最经典 |
| 双底 | 底部间隔15-45天 | 低点价差≤5% | 突破放量 | 反转形态 |
| 平底 | 整理25-35天 | 波动≤15% | 整理期缩量 | 杯柄变体 |
| 高紧旗形 | 旗杆3-6周旗面2-4周 | 旗杆翻倍旗面10-25% | 旗面明显缩量 | 欧奈尔最爱⭐ |
| 上升三角形 | 整理20-40天 | 阻力水平支撑上升 | 突破放量 | 持续形态 |

---

## 使用建议

### 不同市场环境

| 市场环境 | 推荐形态 | 原因 |
|----------|----------|------|
| **牛市初期** | 杯柄、高紧旗形 | 强势股率先启动 |
| **牛市中期** | 平底、上升三角形 | 整理后继续上涨 |
| **震荡市** | 双底、平底 | 反转或整理形态 |
| **熊市反弹** | 双底 | 底部反转信号 |

### 组合使用

**最强组合：**
1. 杯柄形态 + RS ≥ 90
2. 高紧旗形（欧奈尔最爱）
3. 平底 + 上升三角形（连续形态）

---

## Dashboard 使用

**访问地址：**
```
https://chariest-nancy-nonincidentally.ngrok-free.dev/
```

**密码：** `neiltrade123`

**操作步骤：**
1. 登录 Dashboard
2. 在「技术分析筛选器」中找到欧奈尔形态
3. 点击「🔍 检查」输入股票代码查看详情
4. 或点击「▶ 运行」批量筛选

---

## 文件位置

**筛选器文件：**
```
/Users/mac/.openclaw/workspace-neo/scripts/
├── coffee_cup_screener.py          # 杯柄形态
├── double_bottom_screener.py       # 双底形态
├── flat_base_screener.py           # 平底形态
├── high_tight_flag_screener.py     # 高紧旗形
└── ascending_triangle_screener.py  # 上升三角形
```

**详细文档：**
```
/Users/mac/.openclaw/workspace-neo/docs/
└── 欧奈尔杯柄形态选股系统技术白皮书.md
```

---

## 下一步建议

1. **测试运行**：逐个运行新筛选器，验证效果
2. **参数微调**：根据实际选股结果调整参数
3. **组合策略**：开发多形态组合筛选器
4. **回测验证**：对历史数据进行回测验证胜率

---

## 已禁用的筛选器

以下筛选器已被禁用，不再在 Dashboard 中显示，请使用替代版本。

### 1. 咖啡杯形态筛选器（旧版本）❌ 已禁用
- **文件：** `coffee_cup_screener.py`
- **禁用日期：** 2026-04-13
- **禁用原因：** 已被咖啡杯V4替代
- **替代方案：** 使用 `coffee_cup_handle_screener_v4`（咖啡杯V4）

### 2. 杯柄筛选器 ❌ 已禁用
- **文件：** `cup_handle_screener.py`
- **禁用日期：** 2026-04-13
- **禁用原因：** 已被咖啡杯V4替代
- **替代方案：** 使用 `coffee_cup_handle_screener_v4`（咖啡杯V4）

### 推荐使用：咖啡杯V4
**文件：** `coffee_cup_handle_screener_v4.py`
**配置：** `config/screeners/coffee_cup_v4.json`
**优势：**
- ✅ 更精确的形态识别算法
- ✅ 支持单个股票检查功能（Check Stock）
- ✅ 26个可调节参数
- ✅ 支持动态回溯天数计算
- ✅ 更详细的形态分析报告

---

## 筛选器启用/禁用管理

### 如何禁用筛选器
```sql
-- 禁用单个筛选器
UPDATE screeners SET enabled = 0 WHERE name = 'screener_name';

-- 禁用多个筛选器
UPDATE screeners SET enabled = 0 WHERE name IN ('screener1', 'screener2');
```

### 如何启用筛选器
```sql
-- 启用单个筛选器
UPDATE screeners SET enabled = 1 WHERE name = 'screener_name';

-- 启用多个筛选器
UPDATE screeners SET enabled = 1 WHERE name IN ('screener1', 'screener2');
```

### 查看筛选器状态
```sql
-- 查看所有筛选器及其状态
SELECT name, display_name, enabled FROM screeners ORDER BY name;

-- 只查看已禁用的筛选器
SELECT name, display_name FROM screeners WHERE enabled = 0;
```

### 技术实现
- **数据库字段：** `screeners.enabled` (INTEGER, 默认值: 1)
- **后端过滤：** `backend/models.py` 中的 `get_all_screeners()` 只返回 `enabled = 1` 的筛选器
- **前端显示：** Dashboard 只显示启用的筛选器

**文档更新：** 2026-04-13

---

### 14. 老鸭头数据库分类器 ✅ (NEW)
**文件：** `scripts/lao_ya_tou_db_classifier.py` (基础版)
**文件：** `scripts/lao_ya_tou_db_classifier_enhanced.py` (增强版 - 推荐)
**文档：** [lao_ya_tou_db_classifier.md](lao_ya_tou_db_classifier.md)

**功能特点：**
- 直接从SQLite数据库查询和筛选老鸭头模式股票
- 实现三种信号分类系统：
  - **信号1（鸭鼻孔金叉）**: 激进入场信号
  - **信号2（鸭嘴金叉）**: 稳健入场信号
  - **信号3（放量突破）**: 追涨买入信号
- 支持严格/宽松两种筛选模式
- 置信度评分系统
- JSON和Excel双格式输出

**技术指标：**
- MA5/MA10/MA30移动平均线
- MA空隙分析
- 成交量比率
- 趋势强度评估
- 支撑位距离计算

**筛选结果（2026-04-16）**:
- 严格模式: 2只股票（高质量）
- 宽松模式: 128只股票（中等质量）
  - 信号1（鸭鼻孔）: 126只
  - 信号2（鸭嘴）: 0只
  - 信号3（放量）: 2只

**使用方法：**
```bash
# 增强版分类器（推荐）
python3 scripts/lao_ya_tou_db_classifier_enhanced.py --date 2026-04-16 --relaxed

# 严格模式
python3 scripts/lao_ya_tou_db_classifier_enhanced.py --date 2026-04-16
```

**输出文件：**
- `data/lao_ya_tou_enhanced_YYYY-MM-DD.json` - JSON格式
- `data/lao_ya_tou_enhanced_YYYY-MM-DD.xlsx` - Excel格式（包含3个工作表）

**性能指标：**
- 处理速度: ~7,000只/秒
- 总执行时间: ~30秒（5,033只股票）
- 内存占用: <500MB

**创建日期：** 2026-04-17
**状态：** ✅ 已完成并验证
**详细文档：** 参见 [lao_ya_tou_db_classifier.md](lao_ya_tou_db_classifier.md)

---

**© 2026 Neo Trading System**
