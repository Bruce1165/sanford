# 老鸭头筛选器三套信号体系扩展计划

**创建日期：** 2026-04-16
**版本：** V3.0
**状态：** 计划完成

---

## 一、扩展计划概述

实现完整的三套信号体系，避免版本混乱：
- **信号一：** 激进买点・鸭鼻孔缩量金叉（左侧低吸）
- **信号二：** 核心主买・鸭嘴开口金叉（稳健最优）
- **信号三：** 加速追买・放量突破鸭头前高（右侧主升）

---

## 二、要求说明

### 2.1 参数配置要求
**必须明确说明：**
- 代码文件不使用中文（仅英文变量、函数名、注释）
- 参数配置的 display_name 和 description 使用中文说明参数意义
- get_parameter_schema 返回的参数定义使用中文

### 2.2 模块化要求
**当代码逻辑及其复杂的时候，需要运用多个文件，模块化完成整个逻辑**

### 2.3 编码规范要求
**必须遵循项目编码以及其他涉及到编码的要求**

---

## 三、模块化设计

### 3.1 文件组织结构

screeners/
├── lao_ya_tou_zhou_xian_screener.py       # 主筛选器文件
├── signal_detectors/                            # 信号检测器模块
│   ├── __init__.py                             # 模块初始化
│   ├── base_detector.py                         # 基础检测器
│   ├── signal_1_detector.py                 # 信号一检测器
│   ├── signal_2_detector.py                 # 信号二检测器
│   └── signal_3_detector.py                 # 信号三检测器
├── signal_scoring/                               # 信号评分模块
│   ├── __init__.py
│   ├── confidence_calculator.py             # 置信度计算
│   └── signal_merger.py                     # 信号合并器
└── signal_models/                                 # 信号数据模型
    ├── __init__.py
    ├── signal_types.py                        # 信号类型枚举
    └── signal_detection.py                   # 信号检测数据类

### 3.2 模块职责划分

**base_detector.py：**
- 数据加载和预处理
- MA计算（向量化）
- 局部高点识别
- 成交量统计

**signal_1_detector.py：**
- 鸭鼻孔金叉检测
- 缩量检测
- 置信度计算

**signal_2_detector.py：**
- 鸭嘴开口识别
- 三线多头排列
- 缩量后放量
- 置信度计算

**signal_3_detector.py：**
- 历史高点存储
- 突破检测
- 板块共振检测
- 置信度计算

**signal_merger.py：**
- 收集三套信号检测结果
- 按置信度排序
- 处理并发信号
- 选择最优信号
- 计算止损价和仓位建议

---

## 四、参数配置

### 4.1 参数统计

**向后兼容参数（9个，保留现有行为）：**
1. MA5_PERIOD - MA5周期（周）
2. MA10_PERIOD - MA10周期（周）
3. MA30_PERIOD - MA30周期（周）
4. LOCAL_HIGH_WINDOW - 局部高点窗口（周）
5. VOLUME_CONTRACTION_THRESHOLD - 缩量阈值（0.5-0.9）
6. MIN_GAP - 最小缺口（%）
7. MAX_GAP - 最大缺口（%）
8. MIN_WEEKS - 最小数据周数
9. TEST_MODE - 测试模式

**新增参数（17个，三套信号体系）：**

**信号开关（3个）：**
10. ENABLE_SIGNAL_1
11. ENABLE_SIGNAL_2
12. ENABLE_SIGNAL_3

**信号一参数（2个）：**
13. SIGNAL_1_MIN_GAP
14. SIGNAL_1_VOLUME_RATIO_MIN

**信号二参数（2个）：**
15. SIGNAL_2_CONFIRM_WEEKS

**信号三参数（2个）：**
16. SIGNAL_3_BREAKOUT_LOOKBACK

**仓位控制参数（6个）：**
17. POSITION_SIZE_SIGNAL_1_MIN
18. POSITION_SIZE_SIGNAL_1_MAX
19. POSITION_SIZE_SIGNAL_2_MIN
20. POSITION_SIZE_SIGNAL_2_MAX
21. POSITION_SIZE_SIGNAL_3_MIN
22. POSITION_SIZE_SIGNAL_3_MAX

**总计：26个参数**

---

## 五、实施步骤

### 6.1 模块化架构搭建
预计时间：1小时

### 6.2 信号一检测器实现
预计时间：1.5小时

### 6.3 信号二检测器实现
预计时间：1.5小时

### 6.4 信号三检测器实现
预计时间：1.5小时

### 6.5 信号合并模块实现
预计时间：1.5小时

### 6.6 集成与测试
预计时间：1小时

---

## 六、验收标准

### 7.1 功能完整性
- 三套信号全部实现
- 参数可正确配置
- 止损和仓位控制生效

### 7.2 性能要求
- 单只检测 < 100ms
- 4000只总筛选 < 10分钟

---

## 七、下一步行动

1. ✅ 扩展计划文档完成
2. ⏳ 代码评审
3. ⏸ 代码实现
4. ⏸ 测试验证
5. ⏸ 文档更新

---

**总计参数：**
- 向后兼容：9个
- 新增：17个
- 总计：26个参数
