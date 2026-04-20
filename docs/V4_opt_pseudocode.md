# V4 咖啡杯柄筛选器 Opt 优化版 - 伪代码

# ========== 数据类定义 ==========

# 类：FilterStats - 过滤条件统计
# 功能：记录每个过滤条件的失败次数，用于分析筛选效果
@dataclass
class FilterStats:
    # 右侧杯沿相关
    right_rim_not_found: int = 0           # 找不到右杯沿
    handle_too_long: int = 0              # 杯柄太长

    # 左侧杯沿相关
    left_rim_not_found: int = 0           # 找不到左杯沿
    price_mismatch: int = 0                # 价格不匹配
    rim_interval_too_long: int = 0        # 杯沿间隔太长
    rim_interval_too_short: int = 0       # 杯沿间隔太短

    # MA5趋势相关
    ma5_trend_failed: int = 0            # MA5趋势检查失败

    # 震荡期相关
    oscillation_price_too_high: int = 0      # 震荡期价格太高

    # 杯深相关
    cup_depth_too_shallow: int = 0         # 杯深太浅
    cup_depth_too_deep: int = 0           # 杯深太深

    # 杯柄相关
    handle_drop_too_large: int = 0         # 杯柄下跌太大
    handle_drop_negative: int = 0            # 杯柄下跌（价格高于右杯沿）

    # 成交量相关
    volume_insufficient: int = 0          # 成交量不足

    # 当前价格相关
    current_price_too_low: int = 0        # 当前价格太低

    # 通过筛选
    passed: int = 0                     # 通过筛选的股票数

    # 总尝试次数
    total_attempts: int = 0

    def reset(self):
        """重置所有统计"""
        # 功能：清零所有计数器
        self.right_rim_not_found = 0
        self.handle_too_long = 0
        self.left_rim_not_found = 0
        self.price_mismatch = 0
        self.rim_interval_too_long = 0
        self.rim_interval_too_short = 0
        self.ma5_trend_failed = 0
        self.oscillation_price_too_high = 0
        self.cup_depth_too_shallow = 0
        self.cup_depth_too_deep = 0
        self.handle_drop_too_large = 0
        self.handle_drop_negative = 0
        self.volume_insufficient = 0
        self.current_price_too_low = 0
        self.passed = 0
        self.total_attempts = 0


# 类：CupDepthDistribution - 杯深分布统计
# 功能：记录被淘汰股票的杯深值，用于分析参数设置合理性
class CupDepthDistribution:
    def __init__(self):
        """初始化杯深分布"""
        # 功能：初始化各个杯深区间的计数
        # 结构：字典，key为杯深区间（如"5%-10%"），value为计数

        # 各杯深区间的计数器
        self.depths = {
            '5%-10%': 0,
            '10%-15%': 0,
            '15%-20%': 0,
            '20%-25%': 0,
            '25%-30%': 0,
            '30%-35%': 0,
            '35%-40%': 0,
            '40%-45%': 0,
            '45%-50%': 0,
            '50%-55%': 0,
            '55%-60%': 0,
            '60%-65%': 0,
            '65%-70%': 0,
            '70%-75%': 0,
        }
        self.total_depths = 0  # 总记录数

    def add_depth(self, depth_pct: float):
        """添加杯深记录"""
        # 参数：depth_pct - 杯深百分比（如0.15表示15%）
        # 功能：将杯深添加到对应的区间计数

        # 步骤：
        # 1. 判断属于哪个区间
        # 2. 对应区间计数 +1
        # 3. 总计数 +1

        if 0 <= depth_pct < 0.10:
            self.depths['5%-10%'] += 1
        elif 0.10 <= depth_pct < 0.15:
            self.depths['10%-15%'] += 1
        elif 0.15 <= depth_pct < 0.20:
            self.depths['15%-20%'] += 1
        elif 0.20 <= depth_pct < 0.25:
            self.depths['20%-25%'] += 1
        elif 0.25 <= depth_pct < 0.30:
            self.depths['30%-35%'] += 1
        elif 0.30 <= depth_pct < 0.35:
            self.depths['35%-40%'] += 1
        elif 0.35 <= depth_pct < 0.40:
            self.depths['40%-45%'] += 1
        elif 0.40 <= depth_pct < 0.45:
            self.depths['45%-50%'] += 1
        elif 0.45 <= depth_pct < 0.50:
            self.depths['50%-55%'] += 1
        elif 0.50 <= depth_pct < 0.55:
            self.depths['55%-60%'] += 1
        elif 0.55 <= depth_pct < 0.60:
            self.depths['60%-65%'] += 1
        elif 0.60 <= depth_pct < 0.65:
            self.depths['65%-70%'] += 1
        elif 0.65 <= depth_pct <= 0.70:
            self.depths['70%-75%'] += 1
        else:
            logger.warning(f"杯深超出范围: {depth_pct*100:.1f}%")

        self.total_depths += 1

    def get_distribution(self) -> dict:
        """获取杯深分布统计"""
        # 功能：返回杯深分布字典
        # 返回：各区间计数和总计数

        return {
            'distribution': self.depths.copy(),
            'total': self.total_depths
        }

    def print_summary(self):
        """打印杯深分布摘要"""
        # 功能：打印各杯深区间的股票数量
        logger.info("=" * 60)
        logger.info("杯深分布统计:")
        for key in sorted(self.depths.keys()):
            logger.info(f"  杯深 {key}: {self.depths[key]} 只")
        logger.info(f"  杯深总数: {self.total_depths}")
        logger.info("=" * 60)


# 类：CoffeeCupHandleParamsV4 - 参数类
class CoffeeCupHandleParamsV4:
    """V4版本咖啡杯柄形态参数"""

    # 杯沿相关
    RIM_INTERVAL_MIN = 45      # 杯沿间隔最小天数
    RIM_INTERVAL_MAX = 250     # 杯沿间隔最大天数
    RIM_PRICE_MATCH_PCT = 0.05   # 杯沿价格匹配度 ±5%
    RIGHT_RIM_SEARCH_DAYS = 13  # 右侧杯沿搜索天数

    # 杯体相关
    CUP_DEPTH_MIN = 0.05      # 杯深最小 5%
    CUP_DEPTH_MAX = 0.70      # 杯深最大 70%
    RAPID_DECLINE_MIN = 5      # 快速下调最少天数
    RAPID_DECLINE_MAX = 60     # 快速下调最多天数
    RAPID_ASCENT_MIN = 5       # 快速上涨最少天数
    RAPID_ASCENT_MAX = 25      # 快速上涨最多天数

    # 杯柄相关
    HANDLE_MAX_DAYS = 13         # 杯柄最大天数
    HANDLE_MAX_DROP_PCT = 2.0    # 杯柄下跌占杯深比例

    # 成交量相关
    VOLUME_COMPARISON_DAYS = 13 # 成交量对比天数
    VOLUME_RATIO_THRESHOLD = 2.0 # 成交量倍数要求

    # 趋势相关
    MA5_TREND_DAYS = 14          # MA5趋势判断天数
    OSCILLATION_PRICE_CEIL_PCT = 1.0 # 震荡期价格上限占左杯沿%

    # 优化相关
    QUICK_SEARCH_MODE = False     # 快速搜索模式（优先T-45）


# 类：CoffeeCupHandleScreenerV4Opt - V4筛选器优化版主类
# 继承：BaseScreener
class CoffeeCupHandleScreenerV4Opt(BaseScreener):
    """咖啡杯柄形态筛选器 V4优化版"""

    # 初始化方法 __init__
    # 参数：db_path, enable_news, enable_llm, enable_progress, params
    # 功能：初始化筛选器，加载配置参数，初始化统计和杯深分布

    # 步骤：
    # 1. 调用父类 __init__
    # 2. 调用 load_screener_config() 加载配置
    # 3. 应用配置到 self.params
    # 4. 初始化 self.stats = FilterStats()
    # 5. 初始化 self.cup_depth_dist = CupDepthDistribution()

    # 方法：get_parameter_schema - 返回参数配置schema
    # 功能：返回用于UI显示的参数配置
    # 返回：字典（嵌套结构）

    # 方法：_get_default_config - 获取默认配置
    # 功能：返回默认参数配置字典
    # 返回：参数字典

    # 方法：calculate_required_days - 计算所需历史数据天数
    # 功能：返回需要的最大天数
    # 公式：杯沿最大间隔 + 右侧杯沿搜索 + 快速上调最多 + 快速上涨最多 + 缓冲

    # 方法：check_ma5_trend - 检查MA5趋势
    # 参数：df, left_rim_idx
    # 返回：(是否通过, 原因/信息)
    # 功能：检查左杯沿前21天MA5是否呈上升趋势
    # 逻辑：后半部分均值 > 前半部分均值

    # ========== 5轮筛选方法 ==========

    # 方法：_round1_find_right_rim - 第1轮：找右侧杯沿
    # 参数：df
    # 返回：{'right_rim_idx', 'right_rim_price', 'handle_length', 'latest_idx'} 或 None
    # 功能：在筛选日期前13天内找最高价作为右杯沿

    # 步骤：
    # 1. 获取最新索引 latest_idx = len(df) - 1
    # 2. 获取最新数据 latest = df.iloc[latest_idx]
    # 3. 提取日期 latest_date = latest['trade_date']
    # 4. 计算搜索窗口 right_rim_search_window = 13
    # 5. 计算搜索范围 right_rim_search_start = max(0, latest_idx - right_rim_search_window)
    # 6. 提取搜索期间数据 right_rim_period = df.iloc[right_rim_search_start:latest_idx+1]
    # 7. 找最高价索引 right_rim_price_idx = right_rim_period['high'].idxmax()
    # 8. 获取最高价 right_rim_price = right_rim_period.loc[right_rim_price_idx, 'high']
    # 9. 计算杯柄长度 handle_length = latest_idx - right_rim_price_idx
    # 10. 统计 total_attempts += 1

    # 11. 验证杯柄长度 handle_length <= 13
    # 11.1 通过：返回结果
    # 11.2 不通过：记录统计 stats.handle_too_long += 1，返回 None

    # 方法：_round2_find_left_rim - 第2轮：找左侧杯沿
    # 参数：df, round1_result
    # 返回：添加 left_rim_idx, left_rim_price, ma5_passed, ma5_reason 的结果 或 None
    # 功能：从T-45开始追溯到T-250找左杯沿

    # 步骤：
    # 1. 获取右杯沿信息 right_rim_idx, right_rim_price = round1_result['right_rim_idx'], round1_result['right_rim_price']
    # 2. 计算搜索范围：search_start = right_rim_idx - 45 (T-45), search_end = right_rim_idx - 250 (T-250)
    # 3. 边界检查：search_start = max(0, search_start), search_end = max(0, search_end)
    # 4. 检查范围有效性：search_start >= search_end 否则返回 None

    # 5. 遍历：从T-45往回找，顺序 T-45, T-46, ..., T-250
    # 6. 对每个候选 left_rim_idx：
    #    6.1 获取价格 left_rim_price = df.iloc[left_rim_idx]['high']
    #    6.2 价格匹配 price_diff_pct = abs(right_rim_price - left_rim_price) / right_rim_price
    #    6.3 局部高点：前后5天最高价
    #         6.3.1 计算窗口 local_window_start = max(0, left_rim_idx - 5)
    #         6.3.2 计算窗口 local_window_end = min(len(df)-1, left_rim_idx + 5)
    #         6.3.3 提取数据 local_period = df.iloc[local_window_start:local_window_end+1]
    #         6.3.4 获取最高价 local_high = local_period['high'].max()
    #    6.3.5 比较 left_rim_price >= local_high
    #    6.3.6 价格匹配 price_diff_pct <= 0.05
    #    6.3.7 记录统计 total_attempts += 1

    #    6.4 MA5检查 ma5_passed, ma5_reason = check_ma5_trend(df, left_rim_idx)
    #    6.5 找到第一个符合条件的即返回

    #    # 返回结果包含所有字段

    # 方法：_round3_validate_cup_depth - 第3轮：验证杯深
    # 参数：df, round2_result
    # 返回：添加 cup_bottom_price, cup_depth 的结果 或 None
    # 功能：验证杯深在5%-70%范围内

    # 步骤：
    # 1. 获取左杯沿信息 left_rim_idx, left_rim_price = round2_result['left_rim_idx'], round2_result['left_rim_price']
    # 2. 获取右杯沿信息 right_rim_idx = round2_result['right_rim_idx']
    # 3. 提取杯体数据 cup_body_period = df.iloc[left_rim_idx:right_rim_idx]
    # 4. 计算杯底 cup_bottom_price = cup_body_period['low'].min()
    # 5. 计算杯深 cup_depth = (left_rim_price - cup_bottom_price) / left_rim_price
    # 6. 验证杯深范围 CUP_DEPTH_MIN <= cup_depth <= CUP_DEPTH_MAX

    # 6.1 通过：返回结果
    # 6.1.1 记录统计 total_attempts += 1
    # 6.1.2 不通过：
    #    6.1.2.1 记录杯深统计 self.cup_depth_dist.add_depth(cup_depth)
    #    6.1.2.2 如果杯深太浅 stats.cup_depth_too_shallow += 1
    #    6.1.2.3 如果杯深太深 stats.cup_depth_too_deep += 1

    # 方法：_round4_validate_pattern - 第4轮：验证杯体结构、杯柄、成交量
    # 参数：df, round3_result
    # 返回：添加 handle_low, handle_drop, volume_ratio 的结果 或 None
    # 功能：验证杯体结构、杯柄、成交量

    # 步骤：
    # 1. 获取关键信息 left_rim_idx, left_rim_price, right_rim_idx, right_rim_price, latest_idx, cup_bottom_price, cup_depth, handle_length

    # 2. 计算杯体宽度 rim_interval = right_rim_idx - left_rim_idx

    # 3. 优化：根据杯深调整快速上涨天数范围
    # 3.1 杯深30%以下：快速上涨5-15天
    # 3.2 杯深30%-50%：快速上涨5-20天
    # 3.3 杯深50%-70%：快速上涨5-25天
    min_ascent = int(cup_depth * 30)
    max_ascent = min(self.params.RAPID_ASCENT_MAX, int(rim_interval * 0.3))

    # 4. 遍历快速下调天数 rapid_decline_days (min_ascent to min(self.params.RAPID_DECLINE_MAX, rim_interval))
    # 5. 遍历快速上涨天数 rapid_ascent_days (min_ascent to max_ascent)

    # 6. 对每种组合验证：
    # 6.1 计算结束索引 decline_end_idx = left_rim_idx + rapid_decline_days
    # 6.2 跳过如果结束索引超出右杯沿
    # 6.3 计算开始索引 ascent_start_idx = right_rim_idx - rapid_ascent_days
    # 6.4 跳过如果开始索引小于等于结束索引

    # 6.5 提取震荡期 oscillate_period = df.iloc[decline_end_idx:ascent_start_idx]
    # 6.6 验证震荡上限 oscillate_high = oscillate_period['high'].max()
    # 6.6.1 跳过如果震荡价格 > 左杯沿价格 * 100%
    # 6.6.2 记录统计：如果太高则 self.stats.oscillation_price_too_high += 1

    # 6.7 计算杯底（重新计算） cup_body_for_depth = df.iloc[left_rim_idx:ascent_start_idx]
    # 6.7.1 提取杯底 temp_cup_bottom = cup_body_for_depth['low'].min()
    # 6.7.2 计算杯深 temp_cup_depth = (left_rim_price - temp_cup_bottom) / left_rim_price

    # 6.7.3 验证杯深范围 CUP_DEPTH_MIN <= temp_cup_depth <= CUP_DEPTH_MAX
    # 6.7.4 记录统计：太浅或太深

    # 6.8 验证杯柄
    # 6.8.1 获取杯柄期间数据 handle_period = df.iloc[right_rim_idx+1:latest_idx+1]
    # 6.8.2 跳过如果杯柄长度为0（基点日=右杯沿）
    # 6.8.3 获取杯柄最低价 handle_low = handle_period['low'].min()
    # 6.8.4 计算安全水位 cup_depth_abs = left_rim_price - temp_cup_bottom
    # 6.8.5 验证杯柄最低价 handle_low >= cup_bottom + cup_depth_abs * 0.5

    # 6.9 计算杯柄下跌 handle_drop = (right_rim_price - handle_low) / right_rim_price
    # 6.9.1 验证下跌为正数（不高于右杯沿价）
    # 6.9.2 记录统计：handle_drop > 0 则 stats.handle_drop_negative += 1
    # 6.9.3 验证下跌范围 handle_drop <= temp_cup_depth * 2.0
    # 6.9.4 记录统计：如果下跌太大 stats.handle_drop_too_large += 1

    # 6.10 验证成交量
    # 6.10.1 获取左成交量窗口 left_vol_start = left_rim_idx
    # 6.10.2 计算左成交量结束 left_vol_end = min(len(df), left_rim_idx + 13)
    # 6.10.3 左成交量期 left_vol_period = df.iloc[left_vol_start:left_vol_end]
    # 6.10.4 右成交量开始 right_vol_start = max(0, right_rim_idx - 13)
    # 6.10.5 右成交量结束 right_vol_end = right_rim_idx
    # 6.10.6 右成交量期 right_vol_period = df.iloc[right_vol_start:right_vol_end]

    # 6.10.7 计算左成交量平均 left_vol_avg = left_vol_period['volume'].mean()
    # 6.10.8 计算右成交量平均 right_vol_avg = right_vol_period['volume'].mean()
    # 6.10.9 验证数据长度左右都>=13天
    # 6.10.10 计算成交量倍数 vol_ratio = right_vol_avg / left_vol_avg
    # 6.10.11 验证左成交量大于0 left_vol_avg > 0
    # 6.10.12 验证倍数范围 vol_ratio >= VOLUME_RATIO_THRESHOLD
    # 6.10.13 记录统计：如果不满足任一条件 stats.volume_insufficient += 1

    # 6.11 找到第一个通过的组合即返回
    # 6.11.1 计算杯柄下跌 handle_drop = (right_rim_price - handle_low) / right_rim_price 如果handle_length==0则0
    # 6.11.2 记录统计 total_attempts += 1
    # 6.11.3 返回完整结果

    # 方法：_round5_validate_current_price - 第5轮：当前价格验证
    # 参数：df, round4_result
    # 返回：添加 latest_price 的结果 或 None
    # 功能：验证当前价格不低于安全水位

    # 步骤：
    # 1. 获取最新价格信息 latest_idx = round4_result['latest_idx'], latest_price = df.iloc[latest_idx]['close']
    # 2. 获取杯底信息 cup_bottom_price, cup_depth, handle_length

    # 3. 特殊处理：handle_length == 0 时跳过验证
    # 4. 计算安全水位 cup_bottom_plus_depth_50pct = cup_bottom_price + cup_depth * 0.5

    # 5. 验证当前价格 latest_price >= cup_bottom_plus_depth_50pct
    # 5.1 通过：返回添加 latest_price
    # 5.1.1 记录统计 total_attempts += 1
    # 5.1.2 不通过：记录统计 stats.current_price_too_low += 1

    # 方法：find_cup_pattern - 组合5轮方法找形态
    # 参数：df, stock_code, stock_name
    # 返回：结果字典 或 None
    # 功能：依次调用5轮方法，全部通过则返回结果

    # 步骤：
    # 1. 调用 _round1_find_right_rim(df)
    # 2. 如果第1轮失败返回 None
    # 2.1 记录统计 stats.right_rim_not_found += 1

    # 3. 调用 _round2_find_left_rim(df, round1_result)
    # 4. 如果第2轮失败返回 None
    # 4.1 记录统计 stats.left_rim_not_found += 1

    # 5. 调用 _round3_validate_cup_depth(df, round2_result)
    # 6. 如果第3轮失败返回 None
    # 6.1 记录统计 stats.cup_depth_too_shallow += 1 或 stats.cup_depth_too_deep += 1

    # 7. 调用 _round4_validate_pattern(df, round3_result)
    # 8. 如果第4轮失败返回 None
    # 8.1 记录统计（根据失败原因）

    # 9. 调用 _round5_validate_current_price(df, round4_result)
    # 10. 如果第5轮失败返回 None
    # 10.1 记录统计 stats.current_price_too_low += 1

    # 11. 全部通过后返回完整结果
    # 11.1 记录统计 stats.passed += 1

    # 方法：screen_stock - 筛选单只股票
    # 参数：stock_code, stock_name, df
    # 返回：结果字典 或 None
    # 功能：计算MA5，调用find_cup_pattern

    # 步骤：
    # 1. 记录尝试次数 stats.total_attempts += 1
    # 2. 计算MA5 df['ma5'] = df['close'].rolling(5).mean()
    # 3. 调用 find_cup_pattern(stock_code, stock_name, df)

    # 方法：run_screening - 运行筛选（主流程）
    # 参数：date_str, force_restart, enable_analysis
    # 返回：结果列表
    # 功能：遍历所有股票调用screen_stock，保存结果

    # 步骤：
    # 1. 设置当前日期 self.current_date = date_str
    # 2. 获取所有股票 stocks = self.get_all_stocks()
    # 3. 初始化统计 self.stats.reset()
    # 4. 遍历每只股票
    # 5. 对每只股票调用 screen_stock
    # 6. 收集结果

    # 方法：print_summary - 打印统计摘要
    # 功能：打印各过滤条件的失败次数和通过数量

    # 步骤：
    # 1. 打印分隔线
    # 2. 打印右侧杯沿统计
    # 3. 打印左侧杯沿统计
    # 4. 打印杯深统计
    # 5. 打印杯柄统计
    # 6. 打印成交量统计
    # 7. 打印当前价格统计
    # 8. 打印通过数量

    # 方法：save_results - 保存结果到Excel
    # 参数：results, column_mapping, target_date
    # 返回：输出文件路径
    # 功能：将筛选结果保存到Excel文件

    # 步骤：
    # 1. 检查结果是否为空
    # 2. 确定输出目录 output_dir = Path(config['OUTPUT_DIR']) / screener_name / target_date
    # 3. 创建输出目录 output_dir.mkdir(parents=True, exist_ok=True)
    # 4. 将结果转换为DataFrame
    # 5. 调整列顺序
    # 6. 保存为Excel with open(output_dir / 'results.xlsx', 'w', engine='openpyxl') as writer
    # 7. 返回路径


# ========== 配置加载 ==========

# 函数：load_screener_config - 加载配置文件
# 功能：从JSON文件加载参数配置
# 返回：参数字典或 None

# 步骤：
# 1. 构建配置文件路径 config_dir = Path(__file__).parent / 'config' / 'screeners'
# 2. 配置文件路径 config_path = config_dir / 'coffee_cup_handle_screener_v4_opt.json'
# 3. 检查文件存在 config_path.exists()
# 4. 如果不存在返回None
# 5. 读取JSON文件 with open(config_path, 'r', encoding='utf-8') as f: config = json.load(f)
# 6. 提取参数 params_config = config.get('parameters', {})
# 7. 提取元数据 metadata = config.get('metadata', {})
# 8. 返回参数字典

# ========== 主函数入口 ==========

# 函数：main
# 功能：程序入口，解析参数，调用筛选器
# 步骤：
# 1. 解析命令行参数 --date, --db-path
# 2. 配置日志 logging.basicConfig
# 3. 打印分隔线
# 4. 打印筛选器信息
# 5. 打印参数摘要（杯沿间隔、快速下调、快速上涨、杯柄、杯深、成交量倍数）
# 6. 创建筛选器实例 screener = CoffeeCupHandleScreenerV4Opt(db_path=args.db_path)
# 7. 调用 run_screening(args.date) 运行筛选
# 8. 保存结果 output_path = screener.save_results(results)
# 9. 打印完成信息和统计摘要 screener.print_summary()
# 10. 返回退出代码

